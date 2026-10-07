// Approach 4 — progressive GPU path tracing (three-gpu-pathtracer, WebGL2 backend).
//
// Same glTF material inputs as approach 1, but with full light transport: soft shadows from sized
// lights, multiple bounces (the band tints the form and vice versa), importance-sampled HDR.
// The build patches the path tracer's diffuse lobe so light that crosses the interference layer carries
// T(θ_in)·T(θ_out), i.e. the same layered physics as approach 2, now as a reference renderer.
import * as THREE from 'three';
import { WebGLPathTracer } from 'three-gpu-pathtracer';

export function createPathTracerApproach( { textures, viewer } ) {

	const params = {
		thickness: 106,
		filmIOR: 2.45,
		baseIOR: 1.58,
		spread: 12,
		coat: 1,
		roughness: 1,
		normalStrength: 1,
		sheen: 0.3,
		bounces: 5,
		resolution: 0.75,
		maxSamples: 512,
	};

	const material = new THREE.MeshPhysicalMaterial( {
		map: textures.albedo,
		normalMap: textures.normal,
		roughnessMap: textures.orm,
		roughness: 1,
		metalness: 0,
		ior: params.baseIOR,
		specularIntensity: 1,
		iridescence: 1,
		iridescenceMap: textures.irid,
		iridescenceIOR: params.filmIOR,
		iridescenceThicknessMap: textures.irid,
		iridescenceThicknessRange: [ 100, 400 ],
		sheen: params.sheen,
		sheenRoughness: 0.55,
		sheenColor: new THREE.Color( 0x9fb3a6 ),
	} );

	function applyThickness( strain ) {

		const d = params.thickness / ( 1 + 0.45 * strain );
		const s = params.spread / 100;
		material.iridescenceThicknessRange = [ d * ( 1 - s ), d * ( 1 + s ) ];

	}
	applyThickness( 0 );

	let pt = null;
	let off = null;
	const dirty = { scene: true, camera: true, lights: true, env: true, materials: true };
	let status = null;

	function ensure( v ) {

		if ( pt ) return;
		pt = new WebGLPathTracer( v.renderer );
		pt.tiles.set( 2, 2 );
		pt.minSamples = 2;
		pt.renderDelay = 0;
		pt.fadeDuration = 200;
		pt.dynamicLowRes = true;
		pt.lowResScale = 0.3;
		pt.textureSize.set( 2048, 1024 );
		pt.bounces = params.bounces;
		pt.filterGlossyFactor = 0.25;
		pt.multipleImportanceSampling = true;
		pt.renderScale = params.resolution;

	}

	return {
		id: 'pathtracer',
		material,
		allowsAnimation: false,
		controls: [
			{ key: 'thickness', label: 'Film thickness', type: 'range', min: 40, max: 600, step: 1, unit: 'nm' },
			{ key: 'filmIOR', label: 'Film IOR', type: 'range', min: 1.2, max: 2.8, step: 0.01 },
			{ key: 'spread', label: 'Thickness variation', type: 'range', min: 0, max: 40, step: 1, unit: '%' },
			{ key: 'roughness', label: 'Roughness scale', type: 'range', min: 0.2, max: 1.6, step: 0.01 },
			{ key: 'bounces', label: 'Light bounces', type: 'range', min: 1, max: 10, step: 1 },
			{ key: 'resolution', label: 'Render scale', type: 'range', min: 0.25, max: 1, step: 0.05 },
			{ key: 'maxSamples', label: 'Stop after samples', type: 'range', min: 16, max: 2048, step: 16 },
		],
		params,
		set( key, value ) {

			params[ key ] = value;
			switch ( key ) {

				case 'filmIOR': material.iridescenceIOR = value; dirty.materials = true; break;
				case 'roughness': material.roughness = value; dirty.materials = true; break;
				case 'thickness': case 'spread': applyThickness( 0 ); dirty.materials = true; break;
				case 'bounces': if ( pt ) pt.bounces = value; if ( pt ) pt.reset(); break;
				case 'resolution': if ( pt ) pt.renderScale = value; if ( pt ) pt.reset(); break;

			}

		},
		activate( v ) {

			v.setBandMaterial( material );
			ensure( v );
			dirty.scene = true;
			off = v.on( ( what ) => {

				if ( what === 'camera' || what === 'resize' ) dirty.camera = true;
				else if ( what === 'light' ) dirty.lights = true;
				else if ( what === 'environment' ) dirty.env = true;
				else if ( what === 'shape' || what === 'stretch' || what === 'restore' ) dirty.scene = true;

			} );

		},
		deactivate( v ) {

			if ( off ) off();
			off = null;
			v.renderer.setRenderTarget( null );

		},
		get samples() {

			return pt ? Math.floor( pt.samples ) : 0;

		},
		get status() {

			return status;

		},
		// bring the path tracer's copies of scene, materials, lights and camera up to date
		sync( v ) {

			if ( dirty.scene ) {

				applyThickness( v.strain );
				v.scene.updateMatrixWorld( true );
				pt.setScene( v.scene, v.camera );
				dirty.scene = dirty.camera = dirty.lights = dirty.env = dirty.materials = false;

			}
			if ( dirty.materials ) {

				pt.updateMaterials();
				dirty.materials = false;

			}
			if ( dirty.env ) {

				pt.updateEnvironment();
				dirty.env = false;

			}
			if ( dirty.lights ) {

				pt.updateLights();
				dirty.lights = false;

			}
			if ( dirty.camera ) {

				pt.updateCamera();
				dirty.camera = false;

			}

		},
		render( v ) {

			this.sync( v );
			if ( pt.samples < params.maxSamples ) pt.renderSample();
			status = `${Math.floor( pt.samples )} samples`;

		},
		async renderForCapture( v, { samples = 64 } = {} ) {

			dirty.camera = true;
			this.sync( v );
			const prevFade = pt.fadeDuration, prevMin = pt.minSamples, prevLow = pt.dynamicLowRes;
			pt.fadeDuration = 0;
			pt.minSamples = 0;
			pt.dynamicLowRes = false;
			pt.updateCamera();
			let guard = 0;
			while ( pt.samples < samples && guard ++ < samples * 8 ) {

				pt.renderSample();
				if ( guard % 4 === 0 ) await new Promise( ( r ) => setTimeout( r, 0 ) );

			}
			pt.fadeDuration = prevFade;
			pt.minSamples = prevMin;
			pt.dynamicLowRes = prevLow;
			dirty.camera = true;

		},
		describe() {

			return {
				model: 'three-gpu-pathtracer (WebGL2) with glTF iridescence + patched film-transmission diffuse',
				film_ior: params.filmIOR, film_thickness_nm: params.thickness, thickness_variation_pct: params.spread,
				base_ior: params.baseIOR, roughness_scale: params.roughness, bounces: params.bounces,
				samples: pt ? Math.floor( pt.samples ) : 0,
			};

		},
	};

}
