// Turns the procedural band maps into three.js textures. Generation runs in a Web Worker when possible.
import * as THREE from 'three';
import { generateBandMaps } from './band.js';

/* global __MAPS_WORKER_SRC__ */

function generateInWorker( opts ) {

	return new Promise( ( resolve, reject ) => {

		let src = null;
		try {

			src = typeof __MAPS_WORKER_SRC__ === 'string' ? __MAPS_WORKER_SRC__ : null;

		} catch ( e ) {

			src = null;

		}
		if ( ! src || typeof Worker === 'undefined' ) {

			resolve( generateBandMaps( opts ) );
			return;

		}
		let url;
		try {

			url = URL.createObjectURL( new Blob( [ src ], { type: 'text/javascript' } ) );
			const worker = new Worker( url );
			worker.onmessage = ( e ) => {

				worker.terminate();
				URL.revokeObjectURL( url );
				resolve( e.data );

			};
			worker.onerror = () => {

				worker.terminate();
				URL.revokeObjectURL( url );
				resolve( generateBandMaps( opts ) );

			};
			worker.postMessage( opts );

		} catch ( err ) {

			if ( url ) URL.revokeObjectURL( url );
			try {

				resolve( generateBandMaps( opts ) );

			} catch ( e2 ) {

				reject( e2 );

			}

		}

	} );

}

export async function createBandTextures( renderer, { brickPitch, quality = 'high' } = {} ) {

	const size = quality === 'high' ? { width: 2048, height: 1024 } : { width: 1024, height: 512 };
	const maps = await generateInWorker( { ...size, brickPitch } );
	const aniso = renderer.capabilities.getMaxAnisotropy();
	const mk = ( data, colorSpace ) => {

		const t = new THREE.DataTexture( data, maps.width, maps.height, THREE.RGBAFormat, THREE.UnsignedByteType );
		t.wrapS = THREE.RepeatWrapping;
		t.wrapT = THREE.ClampToEdgeWrapping;
		t.magFilter = THREE.LinearFilter;
		t.minFilter = THREE.LinearMipmapLinearFilter;
		t.generateMipmaps = true;
		t.anisotropy = Math.min( 16, aniso );
		t.colorSpace = colorSpace;
		t.flipY = false;
		t.needsUpdate = true;
		return t;

	};
	return {
		maps,
		albedo: mk( maps.albedo, THREE.SRGBColorSpace ),
		normal: mk( maps.normal, THREE.NoColorSpace ),
		orm: mk( maps.orm, THREE.NoColorSpace ),
		irid: mk( maps.irid, THREE.NoColorSpace ),
		tileW: maps.tileW,
	};

}
