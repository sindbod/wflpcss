// Procedural equirectangular HDR environments (linear radiance, Float32 RGBA, row 0 = bottom / -Y).
// Direction convention matches three.js equirect sampling: u = atan2(z, x) / 2π + 0.5, v = asin(y) / π + 0.5.
// The default camera looks at the band from +Z, so "toward the camera" is φ = +90°.

const DEG = Math.PI / 180;

function sstep( e0, e1, x ) {

	const t = Math.min( 1, Math.max( 0, ( x - e0 ) / ( e1 - e0 ) ) );
	return t * t * ( 3 - 2 * t );

}

function angDiff( a, b ) {

	let d = a - b;
	while ( d > Math.PI ) d -= 2 * Math.PI;
	while ( d < - Math.PI ) d += 2 * Math.PI;
	return d;

}

// A rectangular soft light centred at (phi, theta) with angular size (w, h) in degrees.
function softbox( phi, theta, cphi, ctheta, w, h, edge = 2.5, hot = 0.25 ) {

	const dx = angDiff( phi, cphi * DEG ) * Math.cos( theta ) / DEG;
	const dy = ( theta - ctheta * DEG ) / DEG;
	const mx = sstep( w / 2 + edge, w / 2 - edge, Math.abs( dx ) );
	const my = sstep( h / 2 + edge, h / 2 - edge, Math.abs( dy ) );
	const m = mx * my;
	if ( m <= 0 ) return 0;
	const r = Math.hypot( dx / ( w / 2 ), dy / ( h / 2 ) );
	return m * ( 1 + hot * ( 1 - Math.min( 1, r ) ) );

}

const PRESETS = {

	studio( phi, theta, out ) {

		// Fashion e-commerce rig reconstructed from the reference photo (default camera looks from φ ≈ 66°):
		// key softbox ~40° camera-left, rim strip behind-left, weaker fill camera-right, white sweep behind,
		// no light on the camera axis (that is where the photo shows the cream "flop" colour).
		// Calibrated so a white Lambertian surface facing the key reads ~0.85 before tone mapping.
		const y = Math.sin( theta );
		const base = 0.045 + 0.02 * sstep( - 0.1, - 0.5, y ) - 0.015 * sstep( 0.2, 0.9, y );
		let r = base, g = base, b = base * 1.02;
		const sweep = softbox( phi, theta, - 114, 5, 150, 70, 12, 0.1 );
		r += 0.6 * sweep; g += 0.6 * sweep; b += 0.615 * sweep;
		const key = softbox( phi, theta, 106, 14, 46, 72, 4, 0.3 );
		r += 2.6 * key; g += 2.55 * key; b += 2.45 * key;
		const rim = softbox( phi, theta, 168, 10, 16, 80, 3, 0.15 );
		r += 2.2 * rim; g += 2.2 * rim; b += 2.25 * rim;
		const fill = softbox( phi, theta, 30, 8, 36, 60, 4, 0.2 );
		r += 0.75 * fill; g += 0.75 * fill; b += 0.78 * fill;
		const top = softbox( phi, theta, 66, 70, 60, 18, 4, 0.2 );
		r += 1.2 * top; g += 1.2 * top; b += 1.22 * top;
		// white bounce card below the camera
		const card = softbox( phi, theta, 66, - 18, 50, 20, 6, 0 );
		r += 0.35 * card; g += 0.35 * card; b += 0.35 * card;
		out[ 0 ] = r; out[ 1 ] = g; out[ 2 ] = b;

	},

	darkroom( phi, theta, out ) {

		const y = Math.sin( theta );
		const base = 0.0035 + 0.003 * sstep( 0.0, - 0.6, y );
		// a faint door-gap line far away so reflections are not pure black
		const gap = softbox( phi, theta, - 120, - 8, 1.2, 40, 0.5, 0 );
		out[ 0 ] = base + 0.25 * gap; out[ 1 ] = base + 0.24 * gap; out[ 2 ] = base + 0.22 * gap;

	},

	neon( phi, theta, out ) {

		const y = Math.sin( theta );
		const base = 0.012 + 0.012 * sstep( 0.3, - 0.6, y );
		let r = base * 0.8, g = base * 0.85, b = base * 1.4;
		const mag = softbox( phi, theta, 138, 5, 5, 64, 1.2, 0.3 );
		const mag2 = softbox( phi, theta, 152, 5, 5, 64, 1.2, 0.3 );
		r += 13 * ( mag + mag2 ); g += 1.3 * ( mag + mag2 ); b += 6.5 * ( mag + mag2 );
		const cyan = softbox( phi, theta, 35, 10, 6, 60, 1.2, 0.3 );
		r += 1.0 * cyan; g += 8 * cyan; b += 12 * cyan;
		const warm = softbox( phi, theta, 90, 58, 80, 3, 0.8, 0 );
		r += 5 * warm; g += 2.9 * warm; b += 1.1 * warm;
		const blue = softbox( phi, theta, - 90, 10, 120, 40, 20, 0 );
		r += 0.04 * blue; g += 0.06 * blue; b += 0.16 * blue;
		out[ 0 ] = r; out[ 1 ] = g; out[ 2 ] = b;

	},

};

export const PROCEDURAL_ENVS = Object.keys( PRESETS );

export function generateEnvironment( name, width = 1024, height = 512 ) {

	const fn = PRESETS[ name ];
	const data = new Float32Array( width * height * 4 );
	const tmp = [ 0, 0, 0 ];
	for ( let j = 0; j < height; j ++ ) {

		const theta = ( ( j + 0.5 ) / height - 0.5 ) * Math.PI;
		for ( let i = 0; i < width; i ++ ) {

			const phi = ( ( i + 0.5 ) / width - 0.5 ) * 2 * Math.PI;
			fn( phi, theta, tmp );
			const o = ( j * width + i ) * 4;
			data[ o ] = tmp[ 0 ]; data[ o + 1 ] = tmp[ 1 ]; data[ o + 2 ] = tmp[ 2 ]; data[ o + 3 ] = 1;

		}

	}
	return { data, width, height };

}
