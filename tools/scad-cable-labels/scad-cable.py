import argparse
import concurrent.futures
import csv
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScadLabel:
    """Class to generate a single cable label."""

    text: str
    diameter_mm: float
    font_name: str
    scad_file = "cable-label.scad"
    enable_textmetrics = True  # needs to be True for the label generator

    def _get_output_path(self, out_dir):
        """Generate output path based on text and diameter value."""
        filename = f"{self.text.strip().replace(' ', '_')}-{self.diameter_mm}.stl"
        return Path(out_dir) / filename

    @staticmethod
    def _get_flattended_cmd(cmd_raw):
        """Transform nested list of parameters into a flat list for subprocess.run."""
        cmd_flattened = []
        for item in cmd_raw:
            if not item:  # drop None elements from input
                continue
            if isinstance(item, (list, tuple)):
                cmd_flattened.extend(item)
            else:
                cmd_flattened.append(item)
        return cmd_flattened

    @staticmethod
    def _scad_param(key: str, value: str | float | int) -> tuple[str, str]:
        """Get properly formatted -D value to set variables in script"""
        if isinstance(value, str):
            param = f'{key}="{value}"'
        else:
            param = f"{key}={value}"
        return "-D", param

    def generate_stl(self, output_dir):
        # fmt: off
        cmd_raw = [
            "openscad",
            self._scad_param("text", self.text),
            self._scad_param("cable_dia", float(self.diameter_mm)),
            self._scad_param("font", self.font_name),
            "--enable=textmetrics" if self.enable_textmetrics else None,
            "--summary", "all",
            "--summary-file", "-",  # give JSON on stdout
            "-o", self._get_output_path(output_dir),
            self.scad_file,
        ]
        # fmt: on
        ret = subprocess.run(self._get_flattended_cmd(cmd_raw), capture_output=True)
        success = 0 == ret.returncode
        _out, _err = ret.stdout.decode(), ret.stderr.decode()
        _json_stats = json.loads(_out) if success else []
        return success


def handle_csv_input(
    csv_path: str | Path,
    font: str,
    output_dir: str,
    threads: int = min(os.cpu_count(), 32),
):
    with open(csv_path) as fp:
        sniffed_dialect = csv.Sniffer().sniff(fp.read(1024))
        fp.seek(0)
        reader = csv.DictReader(
            fp, fieldnames=("text", "diameter"), dialect=sniffed_dialect
        )
        label_instances = [
            ScadLabel(
                text=c_line["text"], diameter_mm=c_line["diameter"], font_name=font
            )
            for c_line in reader
        ]

    if threads > 0:
        with concurrent.futures.ThreadPoolExecutor(
            thread_name_prefix="LabelCreateExecutor", max_workers=threads
        ) as executor:
            futures = {
                executor.submit(label.generate_stl, output_dir)
                for label in label_instances
            }
        concurrent.futures.wait(futures)
    else:
        for label in label_instances:
            label.generate_stl(output_dir)


def openscad_binary_found() -> bool:
    """Return True if the binary was found."""
    ret = subprocess.run(["openscad", "--version"], capture_output=True)
    binary_found = "OpenSCAD" in str(ret.stderr) and ret.returncode == 0
    return binary_found


def get_parsed_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--diameter", "-d", type=float, default=6.0, help="cable diameter in mm"
    )
    parser.add_argument(
        "--font", "-f", default="Bahnschrift", help="Name of font to be used"
    )
    parser.add_argument(
        "--csv",
        required=False,
        help="Path to a CSV file containing several labels at once. Format: label text, diameter",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        required=False,
        default=".",
        help="path to the output directory",
    )
    parser.add_argument("text", nargs="*", help="Text of the label")
    return parser.parse_args()


def run_main():
    parsed_args = get_parsed_args()

    if not openscad_binary_found():
        raise EnvironmentError("unable to find openscad binary, please add to PATH")
    output_dir = parsed_args.output_dir

    if parsed_args.csv:
        handle_csv_input(parsed_args.csv, parsed_args.font, output_dir)
    else:  # single label mode
        # text from arguments may be a list if separated by spaces
        text = " ".join(parsed_args.text)
        label = ScadLabel(
            text=text, font_name=parsed_args.font, diameter_mm=parsed_args.diameter
        )
        label.generate_stl(output_dir)


if __name__ == "__main__":
    run_main()
