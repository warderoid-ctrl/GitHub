# FluidNC Configuration files.

These are configuration files for [FluidNC](https://github.com/bdring/FluidNC). You can find a full description of the format on the [FluidNC wiki](http://wiki.fluidnc.com/en/config/overview).

## Official

The official files are files that are typically used for firmware testing. They are generally maintained when there are changes or new features added to the config file format. They are not necessarily targeted at any specific machine type or user. 

## Contributed

These are files contributed by users. They are grouped by the target controller. They are not maintained or tested by the FluidNC dev team. Feel free to add your own.

## Config Settings

We have been playing around with the 'run_amps Run current in amps'. All terraPen's sold before 01/12/2024 have this set to 0.2. We have run up to 0.7, but feel 0.5 should be sufficient as a starting point for your own explorations. This change can make your steppers run hotter (so please keep abreast of this!) with a slightly more audible whine, but still rather quiet! This will make your terraPen draw with higher accuracy without any slipping or skipping steps!

It also has the advantage of allowing your 'max_rate_mm_per_min:' to be increased to a whopping 6000 (we got ours at 12000 stable!!). With this increase of feed, we found acceleration settings 'acceleration_mm_per_sec2' to be stable at 750, which permits high move speeds whilst keeping your drawings tight and repeatable, just as you want! (your milage may vary - let us know!)
