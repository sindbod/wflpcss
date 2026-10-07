// Randomised, labelled frame export for training (zip: images/, masks/, labels.jsonl, README.txt).
import { zipSync, strToU8 } from 'fflate';
import { ENVIRONMENTS } from './viewer.js';

export function mulberry32( seed ) {

	let a = seed >>> 0;
	return () => {

		a = ( a + 0x6D2B79F5 ) >>> 0;
		let t = a;
		t = Math.imul( t ^ ( t >>> 15 ), t | 1 );
		t ^= t + Math.imul( t ^ ( t >>> 7 ), t | 61 );
		return ( ( t ^ ( t >>> 14 ) ) >>> 0 ) / 4294967296;

	};

}

const README = `Iridescent band dataset
=======================

images/NNNNN.png   beauty render (sRGB, Khronos PBR Neutral tone mapping)
masks/NNNNN.png    band mask (white = band incl. lining), when exported with masks
labels.jsonl       one JSON object per frame

Coordinates: metres, Y up, band bottom edge at y = 0, front of the band facing +Z.
camera.camera_to_world, camera.world_to_camera and camera.projection are 4x4 matrices as row-major nested
lists; the camera looks down its local -Z axis with +Y up (OpenGL / three.js convention).
camera.intrinsics_px gives fx, fy, cx, cy for the exported image size.
lighting.environment names the HDR (see the page); environment_rotation_deg rotates the whole light rig
(environment and key light) about +Y. key_light.azimuth_deg is relative to the rig.
material holds the approach's physical parameters (film index, thickness in nm, etc.).
`;

function sampleParams( rng, rand, state ) {

	const p = {};
	if ( rand.camera ) {

		p.camera = {
			azimuth: rng() * 360,
			elevation: - 8 + rng() * 40,
			distance: Math.exp( Math.log( 0.12 ) + rng() * ( Math.log( 0.6 ) - Math.log( 0.12 ) ) ),
			fov: 20 + rng() * 20,
		};

	}
	if ( rand.lighting ) {

		const env = ENVIRONMENTS[ Math.floor( rng() * ENVIRONMENTS.length ) ];
		p.env = { id: env.id, rotation: rng() * 360, intensity: 0.7 + rng() * 0.6, keyDefault: env.key };

	}
	if ( rand.key ) {

		const pOn = p.env ? ( p.env.keyDefault ? 0.9 : 0.3 ) : ( state.keyOn ? 1 : 0.5 );
		p.key = {
			on: rng() < pOn,
			azimuth: - 180 + rng() * 360,
			elevation: - 5 + rng() * 65,
			lux: 0.2 + rng() * 1.2,
			size: Math.exp( Math.log( 0.003 ) + rng() * ( Math.log( 0.15 ) - Math.log( 0.003 ) ) ),
		};

	}
	if ( rand.stretch ) p.stretch = rng() * 0.1;
	return p;

}

async function applyParams( viewer, p ) {

	if ( p.env ) {

		if ( viewer.state.env !== p.env.id ) await viewer.setEnvironment( p.env.id );
		viewer.state.envRotation = p.env.rotation;
		viewer.state.envIntensity = p.env.intensity;
		viewer.applyEnvParams();

	}
	if ( p.key ) {

		Object.assign( viewer.state, { keyOn: p.key.on, keyAzimuth: p.key.azimuth, keyElevation: p.key.elevation, keyLux: p.key.lux, keySize: p.key.size } );

	}
	viewer.applyKeyLight();
	if ( p.camera ) {

		viewer.camera.fov = p.camera.fov;
		viewer.camera.updateProjectionMatrix();
		viewer.setCameraSpherical( p.camera.azimuth, p.camera.elevation, p.camera.distance );

	}
	if ( p.stretch != null ) viewer.setStrain( p.stretch );

}

export async function exportDataset( viewer, { approachId, approach, count, size, rand, masks, samples, seed = Date.now() & 0xffff, onProgress } ) {

	const rng = mulberry32( seed );
	const saved = viewer.saveState();
	viewer.paused = true;
	const files = {};
	const lines = [];
	try {

		for ( let i = 0; i < count; i ++ ) {

			const name = String( i ).padStart( 5, '0' );
			const p = sampleParams( rng, rand, viewer.state );
			await applyParams( viewer, p );
			if ( approach.beforeRender ) approach.beforeRender( viewer, 0 );
			const { blob, meta } = await viewer.capture( size, size, { samples } );
			files[ `images/${name}.png` ] = new Uint8Array( await blob.arrayBuffer() );
			if ( masks ) {

				const m = await viewer.captureMask( size, size );
				files[ `masks/${name}.png` ] = new Uint8Array( await m.arrayBuffer() );

			}
			lines.push( JSON.stringify( {
				file: `images/${name}.png`, mask: masks ? `masks/${name}.png` : null, seed, index: i,
				approach: approachId, ...meta, material: approach.describe ? approach.describe() : null,
			} ) );
			onProgress && onProgress( i + 1, count );
			await new Promise( ( r ) => setTimeout( r, 0 ) );

		}

	} finally {

		await viewer.restoreState( saved );
		viewer.paused = false;

	}
	files[ 'labels.jsonl' ] = strToU8( lines.join( '\n' ) + '\n' );
	files[ 'README.txt' ] = strToU8( README );
	return new Blob( [ zipSync( files, { level: 0 } ) ], { type: 'application/zip' } );

}

export async function zipRemoteFiles( base, entries, extra = {} ) {

	const files = {};
	for ( const [ name, rel ] of entries ) {

		const r = await fetch( base + rel );
		if ( r.ok ) files[ name ] = new Uint8Array( await r.arrayBuffer() );

	}
	for ( const [ k, v ] of Object.entries( extra ) ) files[ k ] = typeof v === 'string' ? strToU8( v ) : v;
	return new Blob( [ zipSync( files, { level: 0 } ) ], { type: 'application/zip' } );

}

// Hand a generated file to the viewer. Inside claude.ai this goes through the `downloads` capability
// (the viewer confirms); in a plain browser tab it falls back to a link.
export async function saveFile( filename, blob ) {

	let cap = null;
	try {

		cap = window.claude && typeof window.claude.use === 'function' ? await window.claude.use( 'downloads' ) : null;

	} catch ( e ) {

		cap = null;

	}
	if ( cap ) {

		try {

			const r = await cap.save( { filename, data: blob } );
			return { ok: true, status: r && r.status };

		} catch ( e ) {

			return { ok: false, code: ( e && e.code ) || 'unavailable' };

		}

	}
	if ( window.claude ) return { ok: false, code: 'unavailable' };
	const a = document.createElement( 'a' );
	a.href = URL.createObjectURL( blob );
	a.download = filename;
	document.body.append( a );
	a.click();
	setTimeout( () => {

		URL.revokeObjectURL( a.href );
		a.remove();

	}, 2000 );
	return { ok: true, status: 'link' };

}
