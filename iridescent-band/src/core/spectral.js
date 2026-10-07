// Spectral optics shared by every approach (pure JS, no DOM: also runs in Node).
//
// - CIE 1931 2° colour matching functions (Wyman, Sloan & Shirley 2013 multi-lobe fit)
// - CIE D65 illuminant (10 nm table, linearly interpolated)
// - Airy thin-film reflectance with s/p polarisation and complex substrate index
// - Spectrum -> white-balanced linear sRGB
// - Lookup tables consumed by the real-time shaders

export const LAMBDA_MIN = 380;
export const LAMBDA_MAX = 780;
export const LAMBDA_STEP = 5;
export const LAMBDAS = [];
for ( let l = LAMBDA_MIN; l <= LAMBDA_MAX; l += LAMBDA_STEP ) LAMBDAS.push( l );

const D65_10NM = [
	49.98, 54.65, 82.75, 91.49, 93.43, 86.68, 104.86, 117.01, 117.81, 114.86, 115.92,
	108.81, 109.35, 107.80, 104.79, 107.69, 104.41, 104.05, 100.00, 96.33, 95.79,
	88.69, 90.01, 89.60, 87.70, 83.29, 83.70, 80.03, 80.21, 82.28, 78.28,
	69.72, 71.61, 74.35, 61.60, 69.89, 75.09, 63.59, 46.42, 66.81, 63.38,
]; // 380..780 nm

function lobe( l, mu, s1, s2 ) {

	const s = l < mu ? s1 : s2;
	const t = ( l - mu ) / s;
	return Math.exp( - 0.5 * t * t );

}

export function cmf( l ) {

	const x = 1.056 * lobe( l, 599.8, 37.9, 31.0 ) + 0.362 * lobe( l, 442.0, 16.0, 26.7 ) - 0.065 * lobe( l, 501.1, 20.4, 26.2 );
	const y = 0.821 * lobe( l, 568.8, 46.9, 40.5 ) + 0.286 * lobe( l, 530.9, 16.3, 31.1 );
	const z = 1.217 * lobe( l, 437.0, 11.8, 36.0 ) + 0.681 * lobe( l, 459.0, 26.0, 13.8 );
	return [ x, y, z ];

}

export function d65( l ) {

	const f = ( l - 380 ) / 10;
	const i = Math.max( 0, Math.min( D65_10NM.length - 2, Math.floor( f ) ) );
	const t = Math.min( 1, Math.max( 0, f - i ) );
	return D65_10NM[ i ] * ( 1 - t ) + D65_10NM[ i + 1 ] * t;

}

// XYZ (D65 white) -> linear sRGB
const M = [
	3.2404542, - 1.5371385, - 0.4985314,
	- 0.9692660, 1.8760108, 0.0415560,
	0.0556434, - 0.2040259, 1.0572252,
];

function xyzToRgb( X, Y, Z ) {

	return [
		M[ 0 ] * X + M[ 1 ] * Y + M[ 2 ] * Z,
		M[ 3 ] * X + M[ 4 ] * Y + M[ 5 ] * Z,
		M[ 6 ] * X + M[ 7 ] * Y + M[ 8 ] * Z,
	];

}

// Per-wavelength weights so that  rgb = sum_k W[k] * R(lambda_k)  and a flat R = 1 gives exactly (1,1,1).
export const SPECTRAL_WEIGHTS = ( () => {

	const raw = LAMBDAS.map( ( l ) => {

		const [ x, y, z ] = cmf( l );
		const s = d65( l );
		return xyzToRgb( x * s, y * s, z * s );

	} );
	const white = [ 0, 0, 0 ];
	for ( const w of raw ) for ( let c = 0; c < 3; c ++ ) white[ c ] += w[ c ];
	return raw.map( ( w ) => [ w[ 0 ] / white[ 0 ], w[ 1 ] / white[ 1 ], w[ 2 ] / white[ 2 ] ] );

} )();

export function spectrumToRgb( spectrum ) {

	const out = [ 0, 0, 0 ];
	for ( let k = 0; k < LAMBDAS.length; k ++ ) {

		const w = SPECTRAL_WEIGHTS[ k ];
		const r = spectrum[ k ];
		out[ 0 ] += w[ 0 ] * r; out[ 1 ] += w[ 1 ] * r; out[ 2 ] += w[ 2 ] * r;

	}
	return out;

}

// ---------------------------------------------------------------------------
// Airy thin film: ambient (n1, real) | film (n2, real, thickness d nm) | substrate (n3 + i k3)
// Returns unpolarised reflectance (average of s and p).

function cdiv( ar, ai, br, bi ) {

	const den = br * br + bi * bi;
	return [ ( ar * br + ai * bi ) / den, ( ai * br - ar * bi ) / den ];

}

function csqrt( re, im ) {

	const m = Math.hypot( re, im );
	const r = Math.sqrt( Math.max( 0, ( m + re ) / 2 ) );
	const i = Math.sqrt( Math.max( 0, ( m - re ) / 2 ) ) * ( im < 0 ? - 1 : 1 );
	return [ r, i ];

}

export function airyReflectance( cosTheta, lambda, d, n2, n3, k3 = 0, n1 = 1.0 ) {

	const sin1 = Math.sqrt( Math.max( 0, 1 - cosTheta * cosTheta ) );
	const c1 = cosTheta;
	// film (real index, may be evanescent only if n2 < n1 which we never use)
	const s2 = n1 * sin1 / n2;
	const c2 = Math.sqrt( Math.max( 0, 1 - s2 * s2 ) );
	// substrate complex: cos3 = sqrt(1 - (n1 sin1 / N3)^2)
	const [ inv3r, inv3i ] = cdiv( n1 * sin1, 0, n3, k3 ); // n1 sin1 / N3
	const sq_r = inv3r * inv3r - inv3i * inv3i;
	const sq_i = 2 * inv3r * inv3i;
	const [ c3r, c3i ] = csqrt( 1 - sq_r, - sq_i );

	// r12 (real)
	const r12s = ( n1 * c1 - n2 * c2 ) / ( n1 * c1 + n2 * c2 );
	const r12p = ( n2 * c1 - n1 * c2 ) / ( n2 * c1 + n1 * c2 );

	// r23 complex
	// s: (n2 c2 - N3 c3) / (n2 c2 + N3 c3)
	const N3c3r = n3 * c3r - k3 * c3i;
	const N3c3i = n3 * c3i + k3 * c3r;
	const [ r23sr, r23si ] = cdiv( n2 * c2 - N3c3r, - N3c3i, n2 * c2 + N3c3r, N3c3i );
	// p: (N3 c2 - n2 c3) / (N3 c2 + n2 c3)
	const ar = n3 * c2 - n2 * c3r, ai = k3 * c2 - n2 * c3i;
	const br = n3 * c2 + n2 * c3r, bi = k3 * c2 + n2 * c3i;
	const [ r23pr, r23pi ] = cdiv( ar, ai, br, bi );

	const delta = 4 * Math.PI * n2 * d * c2 / lambda;
	const er = Math.cos( delta ), ei = Math.sin( delta );

	function amp( r12, r23r, r23i ) {

		// (r12 + r23 e) / (1 + r12 r23 e)
		const pr = r23r * er - r23i * ei;
		const pi = r23r * ei + r23i * er;
		const [ qr, qi ] = cdiv( r12 + pr, pi, 1 + r12 * pr, r12 * pi );
		return qr * qr + qi * qi;

	}

	const Rs = amp( r12s, r23sr, r23si );
	const Rp = amp( r12p, r23pr, r23pi );
	return Math.min( 1, Math.max( 0, 0.5 * ( Rs + Rp ) ) );

}

export function filmSpectrum( cosTheta, d, film ) {

	return LAMBDAS.map( ( l ) => airyReflectance( cosTheta, l, d, film.n2, film.n3, film.k3 || 0 ) );

}

// LUTs: x = cos(theta) in [0,1] (columns), y = thickness in [0, dMax] nm (rows).
// Returns Float32Array RGBA for reflectance R and transmittance T = 1 - R (non-absorbing stack).
export function buildFilmLUT( film, { width = 64, height = 256, dMax = 600 } = {} ) {

	const R = new Float32Array( width * height * 4 );
	const T = new Float32Array( width * height * 4 );
	const spec = new Float64Array( LAMBDAS.length );
	for ( let j = 0; j < height; j ++ ) {

		const d = dMax * j / ( height - 1 );
		for ( let i = 0; i < width; i ++ ) {

			const c = Math.max( 1e-3, i / ( width - 1 ) );
			let r0 = 0, r1 = 0, r2 = 0, t0 = 0, t1 = 0, t2 = 0;
			for ( let k = 0; k < LAMBDAS.length; k ++ ) {

				const r = airyReflectance( c, LAMBDAS[ k ], d, film.n2, film.n3, film.k3 || 0 );
				spec[ k ] = r;
				const w = SPECTRAL_WEIGHTS[ k ];
				r0 += w[ 0 ] * r; r1 += w[ 1 ] * r; r2 += w[ 2 ] * r;
				t0 += w[ 0 ] * ( 1 - r ); t1 += w[ 1 ] * ( 1 - r ); t2 += w[ 2 ] * ( 1 - r );

			}
			const o = ( j * width + i ) * 4;
			R[ o ] = Math.max( 0, r0 ); R[ o + 1 ] = Math.max( 0, r1 ); R[ o + 2 ] = Math.max( 0, r2 ); R[ o + 3 ] = 1;
			T[ o ] = Math.max( 0, t0 ); T[ o + 1 ] = Math.max( 0, t1 ); T[ o + 2 ] = Math.max( 0, t2 ); T[ o + 3 ] = 1;

		}

	}
	return { R, T, width, height, dMax };

}

// Normalised monochromatic weights for diffraction: N samples between l0 and l1.
// Each entry is the linear-sRGB contribution of one wavelength bin; the bins sum to (1,1,1).
export function wavelengthBins( n = 16, l0 = 400, l1 = 700 ) {

	const bins = [];
	const sum = [ 0, 0, 0 ];
	for ( let i = 0; i < n; i ++ ) {

		const lc = l0 + ( i + 0.5 ) * ( l1 - l0 ) / n;
		// integrate the bin at 1 nm for a smooth weight
		const acc = [ 0, 0, 0 ];
		const a = l0 + i * ( l1 - l0 ) / n, b = a + ( l1 - l0 ) / n;
		for ( let l = a; l < b; l += 1 ) {

			const [ x, y, z ] = cmf( l + 0.5 );
			const s = d65( l + 0.5 );
			const rgb = xyzToRgb( x * s, y * s, z * s );
			acc[ 0 ] += rgb[ 0 ]; acc[ 1 ] += rgb[ 1 ]; acc[ 2 ] += rgb[ 2 ];

		}
		bins.push( { lambda: lc, rgb: acc } );
		sum[ 0 ] += acc[ 0 ]; sum[ 1 ] += acc[ 1 ]; sum[ 2 ] += acc[ 2 ];

	}
	for ( const b of bins ) b.rgb = b.rgb.map( ( v, c ) => v / sum[ c ] );
	return bins;

}

// 1D table (RGBA float) of normalised spectral weight per nm over [l0, l1]: integrates to (1,1,1).
export function spectralLine( width = 256, l0 = 380, l1 = 780 ) {

	const data = new Float32Array( width * 4 );
	const sum = [ 0, 0, 0 ];
	const raw = [];
	for ( let i = 0; i < width; i ++ ) {

		const l = l0 + ( i + 0.5 ) * ( l1 - l0 ) / width;
		const [ x, y, z ] = cmf( l );
		const s = d65( l );
		const rgb = xyzToRgb( x * s, y * s, z * s );
		raw.push( rgb );
		sum[ 0 ] += rgb[ 0 ]; sum[ 1 ] += rgb[ 1 ]; sum[ 2 ] += rgb[ 2 ];

	}
	const dl = ( l1 - l0 ) / width;
	for ( let i = 0; i < width; i ++ ) {

		// per-nm density so that integral over [l0,l1] of weight dl = 1
		data[ i * 4 ] = raw[ i ][ 0 ] / ( sum[ 0 ] * dl );
		data[ i * 4 + 1 ] = raw[ i ][ 1 ] / ( sum[ 1 ] * dl );
		data[ i * 4 + 2 ] = raw[ i ][ 2 ] / ( sum[ 2 ] * dl );
		data[ i * 4 + 3 ] = 1;

	}
	return { data, width, l0, l1 };

}

// Film presets (n2 = film index, n3 + i k3 = substrate index)
export const FILM_PRESETS = {
	tio2OnMica: { label: 'TiO₂ on mica (interference pigment)', n2: 2.45, n3: 1.58, k3: 0, d: 106 },
	polymerOnPolymer: { label: 'Polymer film on polymer', n2: 1.65, n3: 1.45, k3: 0, d: 420 },
	oxideOnAluminium: { label: 'Oxide on aluminium (foil)', n2: 1.62, n3: 1.2, k3: 7.0, d: 300 },
};

export function linearToSrgb8( v ) {

	const c = Math.min( 1, Math.max( 0, v ) );
	const s = c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow( c, 1 / 2.4 ) - 0.055;
	return Math.round( s * 255 );

}
