# 3d printer cabinet
All projects connected with building a printer enclosure. It is my spin
on the idea of combining a IKEA Platsa corpus with a Sindvik glass door;
unfortunately I don't remember where I saw that approach first and can't
credit my inspiration.

## Features
- glass door, soft close
- LED lights in printer compartment, power supply from printer PSU
- 2 built in electrical outlets in printer compartment
- bottom shelf for filament storage
- LED light in filament storage

### Planned feature:
- fan that regulates temperatures in enclosure and prevents it from overheating
  - should include a simple display with current and set temperture, e.g. this one: https://ardushop.ro/ro/home/1020-modul-display-led-cu-8-cifre-max7219.html
  - should include a simplem method of setting the set temperature e.g. from low...18...65...high
  - should include some kind of control loop, maybe PID controller so that we can react to step inputs like opening the door

## Enclosure body
The body/corpus was built from IKEA parts:

- [Platsa](https://www.ikea.com/ro/ro/p/platsa-cadru-alb-50330946/) corpus 60x55x120cm
- [Sindvik](https://www.ikea.com/ro/ro/p/sindvik-usa-sticla-alb-sticla-transparenta-90291858/) glass door hinge
- [Besta](https://www.ikea.com/ro/ro/p/besta-balama-deschidere-inchidere-lina-80261258/) 
- [Lätthet](https://www.ikea.com/ro/ro/p/laetthet-picior-alb-metal-50395594/) feet
- [Spildra](https://www.ikea.com/ro/ro/p/spildra-parte-superioara-unitate-depozitare-alb-20331693/) shelf top board/cover (optional)
- [hjalpa](https://www.ikea.com/ro/ro/p/hjaelpa-polita-alb-90331166/) shelf (2x)

**Note:** the Sindvik door in the Platsa body is kind of a hack, and this is
why we need to drill our own holes to mount the door. Also: the height of the shelf where the printer sits on is a tiny bit off.

## Sub projects and projects of others used

- [door template](./door-template): a **drill template** that helped me drill holes into 
  the corpus for attaching the doors.
  Notes:
    - please verify the hole position again yourself before actually drilling them.
    - I ended up using slightly different hole positions, but IMO its a good idea
      to make a template like this
- **cable glands**: Here I used [this model](
  https://www.printables.com/model/114283-cable-gland-all-sizes) to 
  print a 7.5mm diameter and 10mm long cable gland to give strain relieve 
  to the power cable (and give the hole a cleaner look).
- **an end cap for cable canals**: see [cable canal end cap](./cable-canal-endcap)
- for the **LED strips**, I designed small **brackets** to hold aluminum channels, plus
  a bracket with a space to hold a switch, see 
  [led-lights-bracket](./led-lights-bracket)
- I needed a **small holder for a switch**, see [switch-holder](./switch-holder). 
  I used hot glue to attach the holder to the back of the enclosure
