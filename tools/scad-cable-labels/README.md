# SCAD cable labels

Idea: call a command line tool with a few parameters, get STL files that are
ready to slice. If more than 1 label is needed, read a simple list and generate
all labels on that list.

## Usage

Run the script with the parameter `--help` to get usage information:

```bash
python scad-cable-label.py --help
```

This will get you this info:

```text
usage: scad-cable-label.py [-h] [--diameter DIAMETER] [--font FONT] [--csv CSV]
                           [--output-dir OUTPUT_DIR]
                           [text ...]

positional arguments:
  text                  Text of the label

options:
  -h, --help            show this help message and exit
  --diameter DIAMETER, -d DIAMETER
                        cable diameter in mm
  --font FONT, -f FONT  Name of font to be used
  --csv CSV             Path to a CSV file containing several labels at once.
                        Format: label text, diameter
  --output-dir OUTPUT_DIR, -o OUTPUT_DIR
                        path to the output directory
```

### CSV mode

In order to create a lot of labels at once, create a CSV file that looks like this:

```csv
SCREEN,6.5
DOCK,6.5
LAPTOP,6.4
DESKTOP,6.5
27W PD,4.0
UPS 1,7.0
```

Note that the file does not contain a header. The script will try to "guess" the
dialect of CSV file used even if the file does not comply with RFC 4180
(looking at you, MS Excel!). In CSV mode, the script will use the same font for 
all labels produced.

## References / License

SCAD script is based on (CC-BY-SA): 
https://www.printables.com/model/606809-configurable-cable-label
