// Band construction and procedural surface maps (pure JS: runs in the browser and in Node).
//
// Measured from the reference photo (band height ~28 mm):
//   bottom fold + plain sage strip | 12 staggered rows of brick cells | seam | rolled sage binding
//   bricks ≈ 3.55 × 1.28 mm on a 1.72 mm row pitch, ≈ 4.3 mm column pitch, half-brick stagger,
//   the lowest rows shrink and break up (halftone fade), the lattice between bricks is raised.

export const BAND = {
	height: 28.0, // mm
	thickness: 1.5, // mm, outer face offset from the body/form
	bottomArc: 1.5,
	patternBottom: 3.2,
	rows: 12,
	rowPitch: 1.80,
	brickW: 3.72,
	brickH: 1.46,
	brickR: 0.56,
	bricksPerTile: 16,
	brickPitchTarget: 4.25,
	seamBottom: 24.95,
	bindingBottom: 25.45,
	bindingTop: 27.0,
	// halftone: brick scale for the lowest rows (row 0 = bottom)
	rowScale: [ 0.42, 0.66, 0.86 ],
	rowDropout: [ 0.32, 0.12, 0.03 ],
};

BAND.patternTop = BAND.patternBottom + BAND.rows * BAND.rowPitch;

// Linear albedos of the ground under the interference layer and of the sage fabric.
export const COLORS = {
	sage: [ 0.268, 0.352, 0.287 ],
	lattice: [ 0.54, 0.515, 0.45 ], // ecru yarn under the interference layer
	brick: [ 0.34, 0.32, 0.28 ],
};

// Cross-section profile: array of { o (outward offset mm), h (height mm) } from the bottom edge to the top edge.
export function bandProfile( segments = 1 ) {

	const pts = [];
	const t0 = BAND.thickness, r0 = BAND.bottomArc;
	// bottom rounded fold
	for ( let i = 0; i <= 8 * segments; i ++ ) {

		const phi = - Math.PI / 2 + ( Math.PI / 2 ) * i / ( 8 * segments );
		pts.push( { o: r0 * Math.cos( phi ) * ( t0 / r0 ), h: r0 + r0 * Math.sin( phi ) } );

	}
	// main face, slightly convex
	const faceN = 46 * segments;
	const h0 = r0, h1 = BAND.seamBottom;
	for ( let i = 1; i <= faceN; i ++ ) {

		const h = h0 + ( h1 - h0 ) * i / faceN;
		pts.push( { o: t0 + 0.22 * Math.sin( Math.PI * ( h - h0 ) / ( h1 - h0 ) ), h } );

	}
	// seam groove
	for ( let i = 1; i <= 4 * segments; i ++ ) {

		const t = i / ( 4 * segments );
		const h = BAND.seamBottom + ( BAND.bindingBottom - BAND.seamBottom ) * t;
		pts.push( { o: t0 - 0.16 * Math.sin( Math.PI * t ), h } );

	}
	// binding rises
	for ( let i = 1; i <= 8 * segments; i ++ ) {

		const t = i / ( 8 * segments );
		const h = BAND.bindingBottom + ( BAND.bindingTop - BAND.bindingBottom ) * t;
		pts.push( { o: t0 + 0.62 * Math.sin( 0.5 * Math.PI * t ), h } );

	}
	// rolled top edge (quarter circle) then the flat top meeting the body
	const rc = BAND.height - BAND.bindingTop; // 1.0
	const oc = t0 + 0.62 - rc;
	for ( let i = 1; i <= 8 * segments; i ++ ) {

		const phi = ( Math.PI / 2 ) * i / ( 8 * segments );
		pts.push( { o: oc + rc * Math.cos( phi ), h: BAND.bindingTop + rc * Math.sin( phi ) } );

	}
	for ( let i = 1; i <= 3; i ++ ) pts.push( { o: oc * ( 1 - i / 3 ), h: BAND.height } );
	return pts;

}

// ---------------------------------------------------------------------------
// Hashing / noise (deterministic, tile-periodic)

function hash2( x, y, seed = 0 ) {

	let h = ( x * 374761393 + y * 668265263 + seed * 2147483647 ) | 0;
	h = Math.imul( h ^ ( h >>> 13 ), 1274126177 );
	h ^= h >>> 16;
	return ( h >>> 0 ) / 4294967295;

}

function smooth( t ) {

	return t * t * ( 3 - 2 * t );

}

// periodic value noise; px = period in lattice cells along x (0 = not periodic)
function vnoise( x, y, px, seed ) {

	const xi = Math.floor( x ), yi = Math.floor( y );
	const fx = x - xi, fy = y - yi;
	const x0 = px ? ( ( xi % px ) + px ) % px : xi;
	const x1 = px ? ( ( ( xi + 1 ) % px ) + px ) % px : xi + 1;
	const a = hash2( x0, yi, seed ), b = hash2( x1, yi, seed );
	const c = hash2( x0, yi + 1, seed ), d = hash2( x1, yi + 1, seed );
	const u = smooth( fx ), v = smooth( fy );
	return a + ( b - a ) * u + ( c - a ) * v + ( a - b - c + d ) * u * v;

}

function fbm( x, y, px, seed, oct = 3 ) {

	let s = 0, a = 0.5, f = 1, n = 0;
	for ( let i = 0; i < oct; i ++ ) {

		s += a * vnoise( x * f, y * f, px * f, seed + i * 17 );
		n += a; a *= 0.5; f *= 2;

	}
	return s / n;

}

function sdRoundBox( px, py, hx, hy, r ) {

	const qx = Math.abs( px ) - hx + r, qy = Math.abs( py ) - hy + r;
	const ox = Math.max( qx, 0 ), oy = Math.max( qy, 0 );
	return Math.hypot( ox, oy ) + Math.min( Math.max( qx, qy ), 0 ) - r;

}

function sstep( e0, e1, x ) {

	const t = Math.min( 1, Math.max( 0, ( x - e0 ) / ( e1 - e0 ) ) );
	return t * t * ( 3 - 2 * t );

}

// ---------------------------------------------------------------------------
// Surface maps for one horizontal tile (bricksPerTile bricks wide, full band height).
//
// Outputs (Uint8 RGBA, row 0 = bottom edge of the band, i.e. v = 0):
//   albedo : sRGB ground colour (sage / white lattice yarn / dark brick recess)
//   normal : tangent-space normal (+x along the band, +y up the band)
//   orm    : R = ambient occlusion, G = roughness, B = metalness
//   irid   : R = interference-coating mask, G = film-thickness deviation (0.5 = nominal),
//            B = brick mask, A = per-cell random
// plus `height` (Float32, mm) for displacement in offline renderers.

export function generateBandMaps( { width = 2048, height = 1024, brickPitch = 4.3, seed = 7 } = {} ) {

	const W = width, H = height;
	const tileW = brickPitch * BAND.bricksPerTile; // mm
	const Hmm = BAND.height;
	const dsPx = tileW / W, dhPx = Hmm / H;

	const hgt = new Float32Array( W * H );
	const zone = new Uint8Array( W * H ); // 0 sage, 1 lattice, 2 brick
	const brickMask = new Float32Array( W * H );
	const cellRand = new Float32Array( W * H );
	const coat = new Float32Array( W * H );
	const thick = new Float32Array( W * H );
	const rough = new Float32Array( W * H );
	const ao = new Float32Array( W * H );
	const knitArr = new Float32Array( W * H );

	// knit lattice periods adjusted so the tile repeats exactly
	const wale = tileW / Math.round( tileW / 0.52 );
	const course = 0.40;
	const nKnitX = Math.round( tileW / 0.52 );
	const irrPeriod = Math.round( tileW / 0.9 ); // yarn irregularity noise
	const irrScale = irrPeriod / tileW;
	const lowPeriod = Math.max( 1, Math.round( tileW / 18 ) );
	const lowScale = lowPeriod / tileW;
	const edgeNoisePeriod = Math.round( tileW / 0.33 );
	const edgeScale = edgeNoisePeriod / tileW;

	const pb = BAND.patternBottom, pt = BAND.patternTop;

	// yarn irregularity / edge wobble / roughness noise on coarse grids (nearest lookup)
	const g4W = Math.ceil( W / 4 ), g4H = Math.ceil( H / 4 ), g2W = Math.ceil( W / 2 ), g2H = Math.ceil( H / 2 );
	const irrGrid = new Float32Array( g4W * g4H ), roughGrid = new Float32Array( g4W * g4H ), edgeGrid = new Float32Array( g2W * g2H );
	for ( let gj = 0; gj < g4H; gj ++ ) for ( let gi = 0; gi < g4W; gi ++ ) {

		const s = ( gi * 4 + 2 ) * dsPx, h = ( gj * 4 + 2 ) * dhPx;
		irrGrid[ gj * g4W + gi ] = vnoise( s * irrScale, h * 1.1, irrPeriod, seed + 3 );
		roughGrid[ gj * g4W + gi ] = vnoise( s * irrScale * 2, h * 2.2, irrPeriod * 2, seed + 77 );

	}
	for ( let gj = 0; gj < g2H; gj ++ ) for ( let gi = 0; gi < g2W; gi ++ ) {

		edgeGrid[ gj * g2W + gi ] = vnoise( ( gi * 2 + 1 ) * dsPx * edgeScale, ( gj * 2 + 1 ) * dhPx * 3.0, edgeNoisePeriod, seed + 9 );

	}

	// slow thickness drift sampled on a coarse grid (8 px cells)
	const gridW = Math.ceil( W / 8 ), gridH = Math.ceil( H / 8 );
	const lowGrid = new Float32Array( gridW * gridH );
	for ( let gj = 0; gj < gridH; gj ++ ) for ( let gi = 0; gi < gridW; gi ++ ) {

		lowGrid[ gj * gridW + gi ] = fbm( ( gi * 8 + 4 ) * dsPx * lowScale, ( gj * 8 + 4 ) * dhPx * 0.07, lowPeriod, seed + 51, 2 );

	}

	for ( let j = 0; j < H; j ++ ) {

		const h = ( j + 0.5 ) * dhPx;
		const inPattern = sstep( pb - 0.25, pb + 0.05, h ) * ( 1 - sstep( pt - 0.05, pt + 0.25, h ) );
		const rowF = ( h - pb ) / BAND.rowPitch;
		const r = Math.floor( rowF );
		const rowValid = r >= 0 && r < BAND.rows;
		const yy = ( h - pb ) - ( r + 0.5 ) * BAND.rowPitch;
		const stagger = ( r & 1 ) ? brickPitch * 0.5 : 0;
		const rowScale = r >= 0 && r < BAND.rowScale.length ? BAND.rowScale[ r ] : 1;
		const rowDrop = r >= 0 && r < BAND.rowDropout.length ? BAND.rowDropout[ r ] : 0;

		for ( let i = 0; i < W; i ++ ) {

			const s = ( i + 0.5 ) * dsPx;
			const idx = j * W + i;

			// --- knit micro relief: jersey stitches, two rounded yarn legs per wale forming a V ---
			const u = s / wale, w = h / course;
			const wi = Math.floor( u ), ci = Math.floor( w );
			const fu = u - wi - 0.5;
			const ry = ( w - ci ) - 0.5; // -0.5 (bottom) .. 0.5 (top) of the course
			const legX = 0.17 + 0.22 * ry; // legs converge toward the bottom of each loop
			const dxl = ( Math.abs( fu ) - legX ) / 0.15;
			const stitchRnd = hash2( ( ( wi % nKnitX ) + nKnitX ) % nKnitX, ci, seed + 5 );
			const irr = ( 0.75 + 0.5 * irrGrid[ ( j >> 2 ) * g4W + ( i >> 2 ) ] ) * ( 0.85 + 0.3 * stitchRnd );
			const yarn = dxl * dxl < 1 ? Math.sqrt( 1 - dxl * dxl ) : 0; // round yarn cross-section
			const knit = yarn * ( 0.82 + 0.18 * Math.cos( Math.PI * ry * 2 ) ) * irr;

			let hv = 0.013 * knit;
			let z = 0;
			let bm = 0;
			let cr = 0;
			let depthN = 0;

			if ( inPattern > 0.001 ) {

				// lattice plateau
				hv += 0.22 * inPattern;
				z = 1;
				if ( rowValid ) {

					const col = Math.floor( ( s + stagger ) / brickPitch );
					const xx = ( s + stagger ) - ( col + 0.5 ) * brickPitch;
					const cid = ( ( col % BAND.bricksPerTile ) + BAND.bricksPerTile ) % BAND.bricksPerTile;
					const rnd = hash2( cid, r, seed );
					const rnd2 = hash2( cid, r, seed + 101 );
					const rnd3 = hash2( cid, r, seed + 211 );
					cr = rnd;
					const dropped = rnd3 < rowDrop;
					if ( ! dropped ) {

						const sc = rowScale * ( 0.96 + 0.08 * rnd2 );
						// broken / fragmentary bricks in the fade rows
						const frag = r < 2 ? ( 0.75 + 0.5 * rnd ) : 1;
						const hx = 0.5 * BAND.brickW * sc * frag;
						const hy = 0.5 * BAND.brickH * Math.min( 1, sc * 1.12 );
						const ox = ( rnd - 0.5 ) * 0.10, oy = ( rnd2 - 0.5 ) * 0.06;
						let d = sdRoundBox( xx - ox, yy - oy, hx, hy, Math.min( BAND.brickR * sc, hy * 0.95 ) );
						d += 0.045 * ( edgeGrid[ ( j >> 1 ) * g2W + ( i >> 1 ) ] - 0.5 );
						// recess: walls ~0.32 mm wide, depth ~0.2 mm, slightly rounded floor
						// shallow, soft recess (the floats sit slightly below the lattice yarn)
						const wall = sstep( 0.06, - 0.5, d );
						depthN = wall;
						hv -= ( 0.055 * wall + 0.006 * knit * wall ) * inPattern;
						bm = sstep( 0.05, - 0.06, d ) * inPattern;
						if ( bm > 0.5 ) z = 2;

					}

				}

			}

			// stitch row along the seam under the binding
			if ( h > BAND.seamBottom - 0.2 && h < BAND.bindingBottom + 0.2 ) {

				const sp = tileW / Math.round( tileW / 0.85 );
				const f = ( s / sp ) - Math.floor( s / sp ) - 0.5;
				const g = ( h - 0.5 * ( BAND.seamBottom + BAND.bindingBottom ) ) / 0.12;
				hv += 0.05 * Math.exp( - f * f / 0.06 - g * g );

			}

			hgt[ idx ] = hv;
			knitArr[ idx ] = Math.min( 1, knit );
			zone[ idx ] = z;
			brickMask[ idx ] = bm;
			cellRand[ idx ] = cr;

			// interference coating: whole pattern zone, fading through the lowest rows
			const fade = sstep( pb - 0.1, pb + 2.2 * BAND.rowPitch, h );
			coat[ idx ] = inPattern * ( 0.35 + 0.65 * fade );

			// thickness deviation: per-brick jitter + slow drift on the lattice
			const low = lowGrid[ ( ( j >> 3 ) * gridW ) + ( i >> 3 ) ];
			thick[ idx ] = 0.5 + 0.18 * ( low - 0.5 ) + bm * ( 0.08 + 0.34 * ( cr - 0.5 ) );

			// roughness
			const rn = roughGrid[ ( j >> 2 ) * g4W + ( i >> 2 ) ];
			const roughSage = 0.80 + 0.06 * ( rn - 0.5 );
			const roughLat = 0.44 + 0.08 * ( rn - 0.5 ) + 0.06 * ( 1 - knit );
			const roughBrick = 0.30 + 0.05 * ( rn - 0.5 );
			const rLat = roughLat + ( roughBrick - roughLat ) * bm;
			rough[ idx ] = roughSage + ( rLat - roughSage ) * inPattern;

			// ambient occlusion: recess depth + knit grooves
			ao[ idx ] = ( 1 - 0.14 * depthN * inPattern ) * ( 0.94 + 0.06 * Math.min( 1, knit ) );

		}

	}

	// --- normal map from the height field (wrap along s, clamp along h) ---
	const normal = new Uint8Array( W * H * 4 );
	for ( let j = 0; j < H; j ++ ) {

		const jm = Math.max( 0, j - 1 ), jp = Math.min( H - 1, j + 1 );
		for ( let i = 0; i < W; i ++ ) {

			const im = ( i - 1 + W ) % W, ip = ( i + 1 ) % W;
			const dhds = ( hgt[ j * W + ip ] - hgt[ j * W + im ] ) / ( 2 * dsPx );
			const dhdh = ( hgt[ jp * W + i ] - hgt[ jm * W + i ] ) / ( ( jp - jm ) * dhPx );
			let nx = - dhds, ny = - dhdh, nz = 1;
			const l = Math.hypot( nx, ny, nz );
			nx /= l; ny /= l; nz /= l;
			const o = ( j * W + i ) * 4;
			normal[ o ] = Math.round( ( nx * 0.5 + 0.5 ) * 255 );
			normal[ o + 1 ] = Math.round( ( ny * 0.5 + 0.5 ) * 255 );
			normal[ o + 2 ] = Math.round( ( nz * 0.5 + 0.5 ) * 255 );
			normal[ o + 3 ] = 255;

		}

	}

	// --- albedo / orm / irid packing ---
	const albedo = new Uint8Array( W * H * 4 );
	const orm = new Uint8Array( W * H * 4 );
	const irid = new Uint8Array( W * H * 4 );
	// sRGB encode via lookup (4096 entries over [0,1])
	const SRGB_LUT = new Uint8Array( 4097 );
	for ( let k = 0; k <= 4096; k ++ ) {

		const c = k / 4096;
		SRGB_LUT[ k ] = Math.round( ( c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow( c, 1 / 2.4 ) - 0.055 ) * 255 );

	}
	const toS = ( v ) => SRGB_LUT[ Math.round( Math.min( 1, Math.max( 0, v ) ) * 4096 ) ];
	const [ sR, sG, sB ] = COLORS.sage, [ lR, lG, lB ] = COLORS.lattice, [ bR, bG, bB ] = COLORS.brick;
	for ( let j = 0; j < H; j ++ ) {

		const h = ( j + 0.5 ) * dhPx;
		const inPattern = sstep( pb - 0.25, pb + 0.05, h ) * ( 1 - sstep( pt - 0.05, pt + 0.25, h ) );
		// ground tint drifts toward sage through the faded lowest rows
		const sageMix = ( 1 - sstep( pb, pb + 2.5 * BAND.rowPitch, h ) ) * 0.55;
		const latR = lR + ( sR * 1.25 - lR ) * sageMix, latG = lG + ( sG * 1.25 - lG ) * sageMix, latB = lB + ( sB * 1.25 - lB ) * sageMix;
		for ( let i = 0; i < W; i ++ ) {

			const idx = j * W + i;
			const o = idx * 4;
			const knitShade = 0.93 + 0.07 * knitArr[ idx ];
			const bm = brickMask[ idx ];
			const pR = latR + ( bR - latR ) * bm, pG = latG + ( bG - latG ) * bm, pB = latB + ( bB - latB ) * bm;
			albedo[ o ] = toS( ( sR + ( pR - sR ) * inPattern ) * knitShade );
			albedo[ o + 1 ] = toS( ( sG + ( pG - sG ) * inPattern ) * knitShade );
			albedo[ o + 2 ] = toS( ( sB + ( pB - sB ) * inPattern ) * knitShade );
			albedo[ o + 3 ] = 255;
			orm[ o ] = Math.round( Math.min( 1, ao[ idx ] ) * 255 );
			orm[ o + 1 ] = Math.round( Math.min( 1, rough[ idx ] ) * 255 );
			orm[ o + 2 ] = 0;
			orm[ o + 3 ] = 255;
			irid[ o ] = Math.round( Math.min( 1, coat[ idx ] ) * 255 );
			irid[ o + 1 ] = Math.round( Math.min( 1, Math.max( 0, thick[ idx ] ) ) * 255 );
			irid[ o + 2 ] = Math.round( bm * 255 );
			irid[ o + 3 ] = Math.round( cellRand[ idx ] * 255 );

		}

	}

	return { width: W, height: H, tileW, brickPitch, albedo, normal, orm, irid, heightMM: hgt, zone };

}
