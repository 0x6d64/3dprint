import argparse
import datetime
import logging
import os
import pathlib
import re
import shutil
import stat
import zipfile
from collections import namedtuple
from dataclasses import dataclass
from typing import List, Union

from setuptools.archive_util import _unpack_zipfile_obj

"""
further improvements:
- complete implementation that compresses old gcode files
"""


_log = logging.getLogger(__name__)
_log.addHandler(logging.StreamHandler())
_log.setLevel(logging.DEBUG)


FolderDate = namedtuple("FolderDate", ["year", "month"])


@dataclass
class CompressionStats:
    uncompressed: float = 0.0
    compressed: float = 0.0
    count: int = 0

    @property
    def ratio(self):
        return self.compressed / self.uncompressed if self.uncompressed else None

    @property
    def saved(self):
        return self.uncompressed - self.compressed

    def __add__(self, other):
        if other == 0:  # happens when we create a sum of the class
            other = CompressionStats()
        return CompressionStats(
            uncompressed=self.uncompressed + other.uncompressed,
            compressed=self.compressed + other.compressed,
            count=self.count + other.count,
        )

    __radd__ = __add__


def remove_readonly(func, path, excinfo_ignored):
    # Using os.chmod with stat.S_IWRITE to allow write permissions
    os.chmod(path, stat.S_IWRITE)
    func(path)


def sizeof_fmt(num: Union[int, float], suffix="B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def get_parsed_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--basedir", help="basedir for search", required=True)
    parser.add_argument(
        "--min-age",
        help="compress from month folders that are this many months old.",
        type=int,
    )
    return parser.parse_args()


def _get_old_monthly_folders(
    basedir: pathlib.Path, min_age_months=1
) -> List[pathlib.Path]:
    retval = []

    if not basedir.exists():
        _log.error(f"basedir is not a dir {basedir}")
    else:
        for item in basedir.iterdir():
            if not item.is_dir():
                continue
            else:
                date = _get_date_from_path(item)
                if not date:
                    continue
                age_in_months = month_difference(
                    datetime.datetime.now().year,
                    datetime.datetime.now().month,
                    date.year,
                    date.month,
                )
                if age_in_months >= min_age_months:
                    _log.info(f"found candidate: {str(item)}")
                    retval.append(item)
                else:
                    _log.debug(f"item too young: {str(item)}")
    return retval


def month_difference(year_a: int, month_a: int, year_b: int, month_b: int) -> int:
    """

    >>> month_difference(2023, 4, 2023, 4)
    0
    >>> month_difference(2023, 4, 2023, 3)
    1
    >>> month_difference(2023, 4, 2022, 4)
    12
    """
    diff = 12 * (year_a - year_b) + (month_a - month_b)
    return diff


def _get_date_from_path(path: pathlib.Path) -> Union[FolderDate, None]:
    folder_pattern = "(?P<year>[0-9]{4})-(?P<month>[0-9]{1,2})"
    match = re.match(folder_pattern, str(path.stem))

    retval = None
    if match:
        retval = FolderDate(
            year=int(match.groupdict().get("year")),
            month=int(match.groupdict().get("month")),
        )
    return retval


def discover_old_input_directories(
    basedir: pathlib.Path, min_age_months=2
) -> list[pathlib.Path]:
    old_month_folder = _get_old_monthly_folders(
        basedir=basedir, min_age_months=min_age_months
    )
    old_input_folders = []
    for month_folder in old_month_folder:
        for project_candidate in month_folder.iterdir():
            if not project_candidate.is_dir():
                continue
            for input_folder_candidate in project_candidate.iterdir():
                if input_folder_candidate.is_dir() and str(
                    input_folder_candidate.stem
                ).startswith("input"):
                    old_input_folders.append(input_folder_candidate)
    return old_input_folders


def get_folder_size(folder: pathlib.Path) -> int:
    size = sum(f.stat().st_size for f in folder.glob("**/*") if f.is_file())
    return size


def _check_archive_for_errors(a: pathlib.Path):
    with zipfile.ZipFile(a) as arch:
        archive_check_has_error = arch.testzip()
        if archive_check_has_error:
            raise RuntimeError(f"bad zipfile {a}")
        else:
            _log.debug(f"success: {str(a)}")


def compress_and_delete_folder(input_list: List[pathlib.Path]) -> CompressionStats:
    size_uncompressed, size_compressed = 0.0, 0.0
    for item in input_list:
        archive_path = shutil.make_archive(
            str(item), format="zip", root_dir=str(item), logger=_log
        )
        _check_archive_for_errors(archive_path)

        item_uncompressed = get_folder_size(item)
        item_compressed = pathlib.Path(archive_path).stat().st_size
        _log.debug(
            f"uncompressed: {sizeof_fmt(item_uncompressed)}, compressed: {sizeof_fmt(item_compressed)}"
        )
        size_uncompressed += item_uncompressed
        size_compressed += item_compressed
        shutil.rmtree(str(item), onerror=remove_readonly)

    return CompressionStats(
        uncompressed=size_uncompressed,
        compressed=size_compressed,
        count=len(input_list) if input_list else 0,
    )


def compress_input_folders(basedir: pathlib.Path, min_age_months=2) -> CompressionStats:
    input_dirs_to_compress = discover_old_input_directories(basedir)
    stats = compress_and_delete_folder(input_dirs_to_compress)
    return stats


def _archive_and_delete_gcode_in_dir(
    input_folder: pathlib.Path, archive_name
) -> CompressionStats:
    all_gcode_files = list(input_folder.glob("*.gcode"))
    all_gcode_sizes = [f.stat().st_size for f in all_gcode_files if f.is_file()]

    if all_gcode_files:
        with zipfile.ZipFile(archive_name, "w", compression=zipfile.ZIP_LZMA) as arch:
            for g_file in all_gcode_files:
                arch.write(g_file, arcname=g_file.name)
        _check_archive_for_errors(archive_name)
        s = CompressionStats(
            uncompressed=sum(all_gcode_sizes),
            compressed=archive_name.stat().st_size,
            count=len(all_gcode_files),
        )
        for g_file in all_gcode_files:
            os.remove(g_file)
    else:  # no gcode file found
        s = CompressionStats()

    return s


def compress_and_delete_gcode_files(
    basedir: pathlib.Path, min_age_months=2
) -> CompressionStats:
    old_month_folders = _get_old_monthly_folders(basedir)
    compression_stats = []
    for month_item in old_month_folders:
        for project__candidate in month_item.iterdir():
            if not project__candidate.is_dir():
                continue
            archive_name = project__candidate.joinpath(
                f"{project__candidate.stem}-gcodearchive.zip"
            )
            c_stat = _archive_and_delete_gcode_in_dir(project__candidate, archive_name)
            compression_stats.append(c_stat)
    return sum(compression_stats)


def run_main(args: argparse.Namespace):
    basedir = pathlib.Path(args.basedir)

    min_age_months = int(args.min_age) if args.min_age else 2

    stats_input_dirs = compress_input_folders(basedir, min_age_months=min_age_months)
    stats_gcode_files = compress_and_delete_gcode_files(
        basedir, min_age_months=min_age_months
    )

    stats = stats_input_dirs + stats_gcode_files

    _log.info(
        f"found {stats.count} items, compressed to {sizeof_fmt(stats.compressed)}, "
        f"ratio: {100 * stats.ratio if stats.ratio else 0.0:2.3}% ({sizeof_fmt(stats.saved)} saved)"
    )


if __name__ == "__main__":
    args = get_parsed_args()
    run_main(args)
