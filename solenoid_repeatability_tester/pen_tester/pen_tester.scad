difference() {

union() {
    cylinder(h=25, r=4, center=true);
    translate([0,0,25])
    cube([8,1.5,25], center=true);
    };
    
// Sensor window
    translate([0,0,30])
    cylinder(h=3, r=3, center=true);
}

