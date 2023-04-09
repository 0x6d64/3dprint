import argparse
import shutil
import logging
import datetime
import pathlib
import re
import os
import stat
import zipfile
from typing import List
from collections import namedtuple
from dataclasses import dataclass

FolderDate = namedtuple("FolderDate", ["year", "month"])


@dataclass
class CompressionStats:
    uncompressed: float
    compressed: float
    count: int

    @property
    def ratio(self):
        return self.compressed / self.uncompressed if self.uncompressed else None

    @property
    def saved(self):
        return self.uncompressed - self.compressed

    def __add__(self, other):
        return CompressionStats(
            uncompressed=self.uncompressed + other.uncompressed,
            compressed=self.compressed + other.compressed,
            count=self.count + other.count,
        )


_log = logging.getLogger(__name__)
_log.addHandler(logging.StreamHandler())
_log.setLevel(logging.DEBUG)


def remove_readonly(func, path, excinfo):
    # Using os.chmod with stat.S_IWRITE to allow write permissions
    os.chmod(path, stat.S_IWRITE)
    func(path)


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def get_parsed_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("--basedir", help="basedir for search", required=True)

    return parser.parse_args()


def _get_old_monthly_folders(
    basedir: pathlib.Path, min_age_months=1
) -> List[pathlib.Path]:
    current_year = datetime.datetime.now().year
    current_month = datetime.datetime.now().month
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
                    current_year, current_month, date.year, date.month
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


def _get_date_from_path(path: pathlib.Path):
    folder_pattern = "(?P<year>[0-9]{4})-(?P<month>[0-9]{1,2})"
    match = re.match(folder_pattern, str(path.stem))

    retval = None
    if match:
        retval = FolderDate(
            year=int(match.groupdict().get("year")),
            month=int(match.groupdict().get("month")),
        )
    return retval


def discover_old_input_directories(basedir: pathlib.Path, min_age_months=2):
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


def compress_and_delete(input_list: List[pathlib.Path]):
    size_uncompressed, size_compressed = 0.0, 0.0
    for item in input_list:
        arch_path = shutil.make_archive(
            str(item), format="zip", root_dir=str(item), logger=_log
        )
        # archive_name = os.path.
        # shutil.make_archive()
        with zipfile.ZipFile(arch_path) as arch:
            arch_check_error = arch.testzip()
            if arch_check_error:
                raise RuntimeError(f"bad zipfile {arch_path}")
            else:
                _log.debug(f"success: {str(arch_path)}")
        item_uncompressed = get_folder_size(item)
        item_compressed = pathlib.Path(arch_path).stat().st_size
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


def get_folder_size(folder: pathlib.Path):
    size = sum(f.stat().st_size for f in folder.glob("**/*") if f.is_file())
    return size


def run_main(args: argparse.Namespace):
    basedir = pathlib.Path(args.basedir)

    input_dirs_to_compress = discover_old_input_directories(basedir)
    stats = compress_and_delete(input_dirs_to_compress)
    _log.info(
        f"found {stats.count} items, compressed to {sizeof_fmt(stats.compressed)}, "
        f"ratio: {100 * stats.ratio if stats.ratio else 0.0:2.3}% ({sizeof_fmt(stats.saved)} saved)"
    )


if __name__ == "__main__":
    args = get_parsed_args()
    run_main(args)
