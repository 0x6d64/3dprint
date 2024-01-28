# 3d printer cabinet
All projects connected with building a printer enclosure.

## Features
- glass door, soft close
- LED lights in printer compartment, power supply from printer PSU
- 2 built in electrical outlets in printer compartment
- bottom shelf for filament storage
- LED light in filament storage (planned later)
- fan that regulates temperatures in enclosure and prevents it from overheating
  - should include a simple display with current and set temperture, e.g. this one: https://ardushop.ro/ro/home/1020-modul-display-led-cu-8-cifre-max7219.html
  - should include a simplem method of setting the set temperature e.g. from low...18...65...high
  - should include some kind of control loop, maybe PID controller so that we can react to step inputs like opening the door
## Enclosure body
The body/copus was built from IKEA parts:

- [Platsa](https://www.ikea.com/ro/ro/p/platsa-cadru-alb-50330946/) corpus 60x55x120cm
- [Sindvik](https://www.ikea.com/ro/ro/p/sindvik-usa-sticla-alb-sticla-transparenta-90291858/) glass door hinge
- [Besta](https://www.ikea.com/ro/ro/p/besta-balama-deschidere-inchidere-lina-80261258/) 
- [Lätthet](https://www.ikea.com/ro/ro/p/laetthet-picior-alb-metal-50395594/) feet
- [Spildra](https://www.ikea.com/ro/ro/p/spildra-parte-superioara-unitate-depozitare-alb-20331693/) shelf top board/cover (optional)
- [hjalpa](https://www.ikea.com/ro/ro/p/hjaelpa-polita-alb-90331166/) shelf (2x)

**Note:** the Sindvik door in the Platsa body is kind of a hack, and this is
why we need to drill our own holes to mount the door. Also: the height of the shelf where the printer sits on is a tiny bit off.
