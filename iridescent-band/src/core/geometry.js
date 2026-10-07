// Band, swatch and display-form geometry. Units: metres, Y up. Band bottom edge at y = 0.
import * as THREE from 'three';
import { BAND, bandProfile } from './band.js';

export const TORSO = {
	A: 0.135, // half width (m)
	B: 0.106, // half depth (m)
	n: 2.25, // superellipse exponent (slightly boxy rib cage)
	taper: 0.8, // relative scale change per metre of height (rib cage narrows downward)
};

function superellipse( t, A, B, n ) {

	const s = Math.sin( t ), c = Math.cos( t ), e = 2 / n;
	return [ A * Math.sign( s ) * Math.pow( Math.abs( s ), e ), B * Math.sign( c ) * Math.pow( Math.abs( c ), e ) ];

}

// Arc-length parametrised closed torso curve at y = 0 (front centre at +Z).
export function torsoCurve( samples = 720 ) {

	const M = 8192;
	const pts = [], cum = [ 0 ];
	for ( let k = 0; k <= M; k ++ ) pts.push( superellipse( 2 * Math.PI * k / M, TORSO.A, TORSO.B, TORSO.n ) );
	for ( let k = 1; k <= M; k ++ ) cum.push( cum[ k - 1 ] + Math.hypot( pts[ k ][ 0 ] - pts[ k - 1 ][ 0 ], pts[ k ][ 1 ] - pts[ k - 1 ][ 1 ] ) );
	const L = cum[ M ];
	const out = [];
	let k = 0;
	for ( let i = 0; i < samples; i ++ ) {

		const target = L * i / samples;
		while ( cum[ k + 1 ] < target ) k ++;
		const f = ( target - cum[ k ] ) / ( cum[ k + 1 ] - cum[ k ] );
		out.push( [ pts[ k ][ 0 ] + ( pts[ k + 1 ][ 0 ] - pts[ k ][ 0 ] ) * f, pts[ k ][ 1 ] + ( pts[ k + 1 ][ 1 ] - pts[ k ][ 1 ] ) * f ] );

	}
	// tangents / outward normals
	const tan = [], nor = [];
	for ( let i = 0; i < samples; i ++ ) {

		const a = out[ ( i - 1 + samples ) % samples ], b = out[ ( i + 1 ) % samples ];
		let tx = b[ 0 ] - a[ 0 ], tz = b[ 1 ] - a[ 1 ];
		const l = Math.hypot( tx, tz );
		tx /= l; tz /= l;
		let nx = tz, nz = - tx;
		if ( nx * out[ i ][ 0 ] + nz * out[ i ][ 1 ] < 0 ) {

			nx = - nx; nz = - nz;

		}
		tan.push( [ tx, tz ] );
		nor.push( [ nx, nz ] );

	}
	return { points: out, tangents: tan, normals: nor, length: L };

}

export function taperScale( y ) {

	return 1 + TORSO.taper * y;

}

// Generic parametric grid: fn(i, j, out) writes xyz. Normals by central differences (wrap in i if closed).
function gridGeometry( Ni, Nj, fn, { closedI = false, uvFn, flip = false } = {} ) {

	const P = new Float32Array( Ni * Nj * 3 );
	const tmp = [ 0, 0, 0 ];
	for ( let i = 0; i < Ni; i ++ ) for ( let j = 0; j < Nj; j ++ ) {

		fn( i, j, tmp );
		const o = ( i * Nj + j ) * 3;
		P[ o ] = tmp[ 0 ]; P[ o + 1 ] = tmp[ 1 ]; P[ o + 2 ] = tmp[ 2 ];

	}
	// add a duplicate column for the UV seam when closed
	const Nc = closedI ? Ni + 1 : Ni;
	const pos = new Float32Array( Nc * Nj * 3 );
	const nor = new Float32Array( Nc * Nj * 3 );
	const tan = new Float32Array( Nc * Nj * 4 );
	const uv = new Float32Array( Nc * Nj * 2 );
	const get = ( i, j ) => {

		const ii = closedI ? ( ( i % Ni ) + Ni ) % Ni : Math.min( Ni - 1, Math.max( 0, i ) );
		const jj = Math.min( Nj - 1, Math.max( 0, j ) );
		const o = ( ii * Nj + jj ) * 3;
		return [ P[ o ], P[ o + 1 ], P[ o + 2 ] ];

	};
	for ( let i = 0; i < Nc; i ++ ) for ( let j = 0; j < Nj; j ++ ) {

		const p = get( i, j );
		const a = get( i - 1, j ), b = get( i + 1, j ), c = get( i, j - 1 ), d = get( i, j + 1 );
		const du = [ b[ 0 ] - a[ 0 ], b[ 1 ] - a[ 1 ], b[ 2 ] - a[ 2 ] ];
		const dv = [ d[ 0 ] - c[ 0 ], d[ 1 ] - c[ 1 ], d[ 2 ] - c[ 2 ] ];
		let n = [ du[ 1 ] * dv[ 2 ] - du[ 2 ] * dv[ 1 ], du[ 2 ] * dv[ 0 ] - du[ 0 ] * dv[ 2 ], du[ 0 ] * dv[ 1 ] - du[ 1 ] * dv[ 0 ] ];
		if ( flip ) n = n.map( ( x ) => - x );
		const ln = Math.hypot( ...n ) || 1;
		const lu = Math.hypot( ...du ) || 1;
		const o = ( i * Nj + j );
		pos.set( p, o * 3 );
		nor.set( [ n[ 0 ] / ln, n[ 1 ] / ln, n[ 2 ] / ln ], o * 3 );
		tan.set( [ du[ 0 ] / lu, du[ 1 ] / lu, du[ 2 ] / lu, flip ? - 1 : 1 ], o * 4 );
		const [ u, v ] = uvFn ? uvFn( i, j ) : [ i / ( Nc - 1 ), j / ( Nj - 1 ) ];
		uv[ o * 2 ] = u; uv[ o * 2 + 1 ] = v;

	}
	const idx = [];
	for ( let i = 0; i < Nc - 1; i ++ ) for ( let j = 0; j < Nj - 1; j ++ ) {

		const a = i * Nj + j, b = ( i + 1 ) * Nj + j, c = ( i + 1 ) * Nj + j + 1, d = i * Nj + j + 1;
		if ( flip ) idx.push( a, d, b, b, d, c );
		else idx.push( a, b, d, b, c, d );

	}
	const g = new THREE.BufferGeometry();
	g.setAttribute( 'position', new THREE.BufferAttribute( pos, 3 ) );
	g.setAttribute( 'normal', new THREE.BufferAttribute( nor, 3 ) );
	g.setAttribute( 'tangent', new THREE.BufferAttribute( tan, 4 ) );
	g.setAttribute( 'uv', new THREE.BufferAttribute( uv, 2 ) );
	g.setIndex( idx );
	return g;

}

// Band worn around the torso form.
export function buildRingBand( { ringSamples = 900, profileSegments = 1 } = {} ) {

	const curve = torsoCurve( ringSamples );
	const prof = bandProfile( profileSegments );
	const Lmm = curve.length * 1000;
	// snap the brick pitch so the pattern closes seamlessly: tiles of 16 bricks
	const nBricks = Math.round( Lmm / BAND.brickPitchTarget / BAND.bricksPerTile ) * BAND.bricksPerTile;
	const brickPitch = Lmm / nBricks;
	const tileW = brickPitch * BAND.bricksPerTile;
	const nTiles = nBricks / BAND.bricksPerTile;
	const lift = 0.0002; // keep the inner edges just off the form surface

	const geo = gridGeometry( ringSamples, prof.length, ( i, j, out ) => {

		const [ cx, cz ] = curve.points[ i ];
		const [ nx, nz ] = curve.normals[ i ];
		const y = prof[ j ].h / 1000;
		const k = taperScale( y );
		const o = prof[ j ].o / 1000 + lift;
		out[ 0 ] = cx * k + nx * o;
		out[ 1 ] = y;
		out[ 2 ] = cz * k + nz * o;

	}, {
		closedI: true,
		uvFn: ( i, j ) => [ nTiles * i / ringSamples, prof[ j ].h / BAND.height ],
	} );
	geo.userData = { brickPitch, tileW, nTiles, lengthMM: Lmm };
	return geo;

}

// Flexing swatch: a straight band segment whose centreline bends and twists over time.
export class FlexSwatch {

	constructor( { length = 0.15, samples = 260, brickPitch = 4.3 } = {} ) {

		this.length = length;
		this.samples = samples;
		this.prof = bandProfile( 1 );
		this.tileW = brickPitch * BAND.bricksPerTile;
		const Nj = this.prof.length;
		this.front = gridGeometry( samples, Nj, ( i, j, out ) => this._point( i, j, out, 0 ), {
			uvFn: ( i, j ) => [ ( i / ( samples - 1 ) ) * length * 1000 / this.tileW, this.prof[ j ].h / BAND.height ],
		} );
		// lining (inner face), flipped
		this.back = gridGeometry( samples, 2, ( i, j, out ) => this._point( i, j === 0 ? 0 : Nj - 1, out, - 0.0002 ), {
			flip: true,
			uvFn: ( i, j ) => [ ( i / ( samples - 1 ) ) * length * 1000 / this.tileW, j ],
		} );
		this.frames = null;
		this.update( 0, { bend: 0.0, twist: 0.0, wave: 0.0 } );

	}

	_point( i, j, out, inset ) {

		const s = this.samples;
		const f = this.frames;
		const p = this.prof[ j ];
		const yOff = ( p.h - BAND.height / 2 ) / 1000;
		const o = p.o / 1000 + inset;
		if ( ! f ) {

			out[ 0 ] = ( i / ( s - 1 ) - 0.5 ) * this.length;
			out[ 1 ] = yOff;
			out[ 2 ] = o;
			return;

		}
		const c = f.C[ i ], N = f.N[ i ], B = f.B[ i ];
		out[ 0 ] = c[ 0 ] + B[ 0 ] * yOff + N[ 0 ] * o;
		out[ 1 ] = c[ 1 ] + B[ 1 ] * yOff + N[ 1 ] * o;
		out[ 2 ] = c[ 2 ] + B[ 2 ] * yOff + N[ 2 ] * o;

	}

	// bend: max curvature (1/m), twist: total twist (rad), wave: travelling ripple amplitude (1/m)
	update( time, { bend = 9, twist = 0.9, wave = 6, speed = 1 } = {} ) {

		const S = this.samples, L = this.length, ds = L / ( S - 1 );
		const mid = ( S - 1 ) / 2;
		const t = time * speed;
		const kappa = ( s ) => bend * Math.sin( 0.55 * t ) + wave * Math.sin( 2 * Math.PI * ( s / L ) * 1.5 - 1.3 * t );
		const tau = twist / L * Math.sin( 0.37 * t + 0.6 );
		const C = new Array( S ), T = new Array( S ), N = new Array( S ), B = new Array( S );
		C[ mid | 0 ] = [ 0, 0, 0 ];
		const midI = Math.floor( mid );
		T[ midI ] = [ 1, 0, 0 ]; N[ midI ] = [ 0, 0, 1 ]; B[ midI ] = [ 0, 1, 0 ];
		const rot = ( v, axis, ang ) => {

			const c = Math.cos( ang ), s = Math.sin( ang );
			const d = v[ 0 ] * axis[ 0 ] + v[ 1 ] * axis[ 1 ] + v[ 2 ] * axis[ 2 ];
			const cr = [ axis[ 1 ] * v[ 2 ] - axis[ 2 ] * v[ 1 ], axis[ 2 ] * v[ 0 ] - axis[ 0 ] * v[ 2 ], axis[ 0 ] * v[ 1 ] - axis[ 1 ] * v[ 0 ] ];
			return [ 0, 1, 2 ].map( ( k ) => v[ k ] * c + cr[ k ] * s + axis[ k ] * d * ( 1 - c ) );

		};
		const step = ( from, to, dir ) => {

			const s = ( from - mid ) * ds;
			const k = kappa( s ) * ds * dir;
			const tw = tau * ds * dir;
			// bend about B (T rotates toward -N: convex toward the viewer), twist about T
			let t1 = rot( T[ from ], B[ from ], - k ), n1 = rot( N[ from ], B[ from ], - k );
			const b1 = rot( B[ from ], t1, tw );
			n1 = rot( n1, t1, tw );
			T[ to ] = t1; N[ to ] = n1; B[ to ] = b1;
			C[ to ] = [ 0, 1, 2 ].map( ( q ) => C[ from ][ q ] + dir * 0.5 * ( T[ from ][ q ] + t1[ q ] ) * ds );

		};
		for ( let i = midI; i < S - 1; i ++ ) step( i, i + 1, 1 );
		for ( let i = midI; i > 0; i -- ) step( i, i - 1, - 1 );
		this.frames = { C, N, B, T };
		this._rebuild( this.front, this.prof.length, 0, false );
		this._rebuild( this.back, 2, - 0.0002, true );

	}

	_rebuild( geo, Nj, inset, isBack ) {

		const pos = geo.attributes.position.array;
		const tmp = [ 0, 0, 0 ];
		for ( let i = 0; i < this.samples; i ++ ) for ( let j = 0; j < Nj; j ++ ) {

			const jj = isBack ? ( j === 0 ? 0 : this.prof.length - 1 ) : j;
			this._point( i, jj, tmp, inset );
			pos.set( tmp, ( i * Nj + j ) * 3 );

		}
		geo.attributes.position.needsUpdate = true;
		recomputeGridNormals( geo, this.samples, Nj, isBack );

	}

}

function recomputeGridNormals( geo, Ni, Nj, flip ) {

	const P = geo.attributes.position.array, Nn = geo.attributes.normal.array, Tt = geo.attributes.tangent.array;
	const g = ( i, j, k ) => P[ ( Math.min( Ni - 1, Math.max( 0, i ) ) * Nj + Math.min( Nj - 1, Math.max( 0, j ) ) ) * 3 + k ];
	for ( let i = 0; i < Ni; i ++ ) for ( let j = 0; j < Nj; j ++ ) {

		const du = [ 0, 1, 2 ].map( ( k ) => g( i + 1, j, k ) - g( i - 1, j, k ) );
		const dv = [ 0, 1, 2 ].map( ( k ) => g( i, j + 1, k ) - g( i, j - 1, k ) );
		let n = [ du[ 1 ] * dv[ 2 ] - du[ 2 ] * dv[ 1 ], du[ 2 ] * dv[ 0 ] - du[ 0 ] * dv[ 2 ], du[ 0 ] * dv[ 1 ] - du[ 1 ] * dv[ 0 ] ];
		if ( flip ) n = n.map( ( x ) => - x );
		const ln = Math.hypot( ...n ) || 1, lu = Math.hypot( ...du ) || 1;
		const o = i * Nj + j;
		Nn[ o * 3 ] = n[ 0 ] / ln; Nn[ o * 3 + 1 ] = n[ 1 ] / ln; Nn[ o * 3 + 2 ] = n[ 2 ] / ln;
		Tt[ o * 4 ] = du[ 0 ] / lu; Tt[ o * 4 + 1 ] = du[ 1 ] / lu; Tt[ o * 4 + 2 ] = du[ 2 ] / lu;

	}
	geo.attributes.normal.needsUpdate = true;
	geo.attributes.tangent.needsUpdate = true;
	geo.computeBoundingSphere();

}

// Neutral display form (dress-form style rib cage section) the band sits on.
export function buildForm( { ringSamples = 240, yBottom = - 0.30, yTop = 0.046, bevel = 0.012 } = {} ) {

	const curve = torsoCurve( ringSamples );
	const rows = [];
	const nSide = 70, nBevel = 24;
	const yBevel = yTop - bevel;
	const kAt = ( y ) => {

		if ( y >= - 0.15 ) return taperScale( y );
		const d = - 0.15 - y; // hip flare below the waist
		return taperScale( - 0.15 ) + 0.55 * d * d / ( d + 0.04 );

	};
	for ( let r = 0; r <= nSide; r ++ ) {

		const y = yBottom + ( yBevel - yBottom ) * r / nSide;
		rows.push( { y, k: kAt( y ), inset: 0 } );

	}
	for ( let r = 1; r <= nBevel; r ++ ) {

		const a = ( Math.PI / 2 ) * r / nBevel;
		rows.push( { y: yBevel + bevel * Math.sin( a ), k: kAt( yBevel ), inset: bevel * ( 1 - Math.cos( a ) ) } );

	}
	// top cap rings toward the centre
	const capRings = 10;
	const last = rows[ rows.length - 1 ];
	for ( let r = 1; r <= capRings; r ++ ) rows.push( { y: yTop, k: last.k * ( 1 - r / capRings * 0.999 ), inset: last.inset * ( 1 - r / capRings ) } );
	return gridGeometry( ringSamples, rows.length, ( i, j, out ) => {

		const [ cx, cz ] = curve.points[ i ];
		const [ nx, nz ] = curve.normals[ i ];
		const row = rows[ j ];
		out[ 0 ] = cx * row.k - nx * row.inset;
		out[ 1 ] = row.y;
		out[ 2 ] = cz * row.k - nz * row.inset;

	}, { closedI: true, uvFn: ( i, j ) => [ i / ringSamples * 6, j / rows.length ] } );

}
