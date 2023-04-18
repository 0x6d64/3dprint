# Helper: SVG to 3dprint
## User story
I want to design flat model that is 3d-printable using color changes. Since
the print should be nice and smooth a vector format is desirable as an input;
SVG seems to be a good format since it can be created e.g. with Inkscape.

The workflow should look like this from the outside:

```mermaid
---
Workflow user perspective
---
flowchart LR
    svg[SVG e.g. from Inkscape] --> script[helper script]
    config[config file] --> script
    script --> 3dfile[STL or Step file\n that is ready for\n slicing.]
```

## Draft of implementation
```mermaid
flowchart TD
    SVG --> n1
    config[config file or\ncommand line parameters] --> n1
    subgraph helper
        n1[analyze svg and assign height to color] --> 
        n2[cut svn into parts for each height] -->
        n3[python code generating open scad code] -->
        n4["call openscad, export open scad to stl or step"]
    end
    helper --> 3dfile[finished printable file]
```

