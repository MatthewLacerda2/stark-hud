// Shared by the tape, which composites it into what a widget drew, and by the
// glass slab, which lays it on the pane itself. One picture of dirt, so the
// glass and the tape never disagree about what dirty looks like.
//
// The dirt, as a picture of dirt rather than as noise.
//
// Two things are going on inside this image, and they are the whole difference
// between dirt and grain.
//
// The turbulence is *coarse* — about thirteen cells across the tile, three
// octaves — so it varies over tens of pixels rather than per pixel. That gives
// patches. Then `feFuncA` throws the low end away: the table is flat at zero
// for the first three fifths of the range and only climbs after that, so the
// bottom of the noise becomes clean glass and only the peaks survive. Measured
// on the rasterised tile, 87% of it is below 0.05 alpha and a surviving pixel
// has 3.45 of its 4 neighbours surviving too, where scattering the same pixels
// at random would give 0.53. Most of the surface is clean and what is left
// collects in clumps of roughly five to twenty-five pixels across.
//
// The colour is a constant warm grey and the alpha carries all the shape, which
// is what the colour matrix does: RGB from the last column, alpha tapped off
// the red channel of the turbulence.
//
// It is an image and not primitives in the filter below for the reason the
// grain before it was: `feTurbulence` inside the board's filter is generated
// per widget over that widget's whole region, and cost about a core and a half.
// Here it is run once, inside a 256px image the browser rasterises and caches,
// and the filter only tiles it. A tile that size is about one widget wide on
// this board, so the repeat usually falls outside the widget showing it.
export const DIRT =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'%3E%3Cfilter id='d' x='0' y='0' width='256' height='256' filterUnits='userSpaceOnUse' color-interpolation-filters='sRGB'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.05' numOctaves='3' seed='7' stitchTiles='stitch'/%3E%3CfeColorMatrix type='matrix' values='0 0 0 0 0.86 0 0 0 0 0.84 0 0 0 0 0.8 1 0 0 0 0'/%3E%3CfeComponentTransfer%3E%3CfeFuncA type='table' tableValues='0 0 0 0 0.35 1'/%3E%3C/feComponentTransfer%3E%3C/filter%3E%3Crect width='256' height='256' filter='url(%23d)'/%3E%3C/svg%3E";
