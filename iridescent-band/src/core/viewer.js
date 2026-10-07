// Shared real-time viewer: scene, camera, light rig, environments, behaviours, capture.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';
import { PhysicalSpotLight } from 'three-gpu-pathtracer';
import { gunzipSync } from 'fflate';
import { buildRingBand, buildForm, FlexSwatch } from './geometry.js';
import { generateEnvironment } from './envgen.js';
import { BAND } from './band.js';

export const ENVIRONMENTS = [
	{ id: 'studio', label: 'Softbox studio (like the photo)', kind: 'procedural', key: true, keyLux: 0.35, keyAzimuth: - 16, keyElevation: 14, keySize: 0.1 },
	{ id: 'darkroom', label: 'Flashlight test (dark room + point light)', kind: 'procedural', key: true, keyLux: 1.3, keyAzimuth: - 14, keyElevation: - 12, keySize: 0.004 },
	{ id: 'neon', label: 'Neon strips (magenta / cyan)', kind: 'procedural', key: false },
	{ id: 'venice_sunset', label: 'Sunset, waterfront', kind: 'file', url: 'hdr/venice_sunset_1k.hdr', key: false },
	{ id: 'blouberg_sunrise', label: 'Low sun, beach sunrise', kind: 'file', url: 'hdr/blouberg_sunrise_2_1k.hdr', key: false },
	{ id: 'quarry', label: 'Hard midday sun', kind: 'file', url: 'hdr/quarry_01_1k.hdr', key: false },
	{ id: 'overpass', label: 'Overcast city', kind: 'file', url: 'hdr/pedestrian_overpass_1k.hdr', key: false },
	{ id: 'bridge', label: 'Shade under a bridge', kind: 'file', url: 'hdr/san_giuseppe_bridge_2k.hdr', key: false },
	{ id: 'night', label: 'Night, artificial light', kind: 'file', url: 'hdr/moonless_golf_1k.hdr', key: true, keyLux: 0.45, keyAzimuth: 35, keyElevation: 30, keySize: 0.03 },
];

export const BAND_CENTER = new THREE.Vector3( 0, BAND.height / 2000, 0 );

const DEFAULT_STATE = {
	shape: 'ring', // 'ring' | 'swatch'
	env: 'studio',
	envRotation: 0, // degrees
	envIntensity: 1,
	background: 'studio', // 'studio' | 'environment' | 'transparent'
	exposure: 1.0,
	keyOn: true,
	keyAzimuth: - 16, // degrees, 0 = from the +Z side (front of the band)
	keyElevation: 14,
	keyLux: 0.35,
	keySize: 0.1, // m, light radius (soft shadows, highlight size)
	orbitCamera: false,
	orbitLight: false,
	spinEnv: false,
	breathe: false,
	flex: true,
	stretch: 0, // static strain (0..0.15)
	breatheAmount: 0.06,
};

export class Viewer {

	constructor( container, { onStatus = () => {} } = {} ) {

		this.container = container;
		this.onStatus = onStatus;
		this.state = { ...DEFAULT_STATE };
		this.envCache = new Map();
		this.time = 0;
		this.timer = new THREE.Timer();
		this.listeners = new Set();
		this.approach = null;
		this.strain = 0;
		this.paused = false;

	}

	init() {

		const canvas = document.createElement( 'canvas' );
		canvas.className = 'viewport-canvas';
		this.container.appendChild( canvas );
		const renderer = new THREE.WebGLRenderer( { canvas, antialias: true, alpha: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' } );
		renderer.setPixelRatio( Math.min( window.devicePixelRatio || 1, 2 ) );
		renderer.outputColorSpace = THREE.SRGBColorSpace;
		renderer.toneMapping = THREE.NeutralToneMapping;
		renderer.toneMappingExposure = this.state.exposure;
		renderer.shadowMap.enabled = true;
		renderer.shadowMap.type = THREE.PCFShadowMap;
		this.renderer = renderer;
		this.canvas = canvas;

		const scene = new THREE.Scene();
		this.scene = scene;
		this.studioColor = new THREE.Color( 0x1b1b1a );
		scene.background = this.studioColor;

		const camera = new THREE.PerspectiveCamera( 28, 1, 0.01, 30 );
		this.camera = camera;
		this.setCameraSpherical( 24, 5, 0.46 );

		const controls = new OrbitControls( camera, canvas );
		controls.target.copy( BAND_CENTER );
		controls.enableDamping = true;
		controls.dampingFactor = 0.08;
		controls.minDistance = 0.06;
		controls.maxDistance = 2.2;
		controls.autoRotateSpeed = 1.2;
		controls.update();
		controls.addEventListener( 'change', () => this.emit( 'camera' ) );
		this.controls = controls;

		// key light: physically sized spot (path tracer uses radius for soft shadows)
		const key = new PhysicalSpotLight( 0xffffff );
		key.angle = 0.42;
		key.penumbra = 0.8;
		key.decay = 2;
		key.distance = 0;
		key.castShadow = true;
		key.shadow.mapSize.set( 2048, 2048 );
		key.shadow.bias = - 0.0001;
		key.shadow.normalBias = 0.0015;
		key.shadow.radius = 4;
		key.shadow.camera.near = 0.3;
		key.shadow.camera.far = 4;
		key.target.position.copy( BAND_CENTER );
		scene.add( key, key.target );
		this.key = key;

		// geometry
		this.ringGeometry = buildRingBand();
		this.brickPitch = this.ringGeometry.userData.brickPitch;
		this.swatch = new FlexSwatch( { brickPitch: this.brickPitch } );

		// matte skin-tone mannequin (the band is worn on skin in the reference)
		this.formMaterial = new THREE.MeshPhysicalMaterial( {
			color: 0xb48a6e, roughness: 0.62, sheen: 0.25, sheenRoughness: 0.5, sheenColor: 0xd2a891,
		} );
		this.liningMaterial = new THREE.MeshPhysicalMaterial( {
			color: 0x7f978a, roughness: 0.82, sheen: 0.5, sheenRoughness: 0.6, sheenColor: 0x8fa597, side: THREE.FrontSide,
		} );
		this.floorMaterial = new THREE.MeshStandardMaterial( { color: 0x1e1d1b, roughness: 0.95 } );

		this.worn = new THREE.Group();
		this.ringMesh = new THREE.Mesh( this.ringGeometry, this.liningMaterial );
		this.ringMesh.castShadow = true;
		this.ringMesh.receiveShadow = true;
		this.formMesh = new THREE.Mesh( buildForm( { yTop: 0.085, bevel: 0.04 } ), this.formMaterial );
		this.formMesh.castShadow = true;
		this.formMesh.receiveShadow = true;
		this.worn.add( this.ringMesh, this.formMesh );

		this.swatchGroup = new THREE.Group();
		this.swatchFront = new THREE.Mesh( this.swatch.front, this.liningMaterial );
		this.swatchBack = new THREE.Mesh( this.swatch.back, this.liningMaterial );
		this.swatchFront.castShadow = this.swatchBack.castShadow = true;
		this.swatchFront.receiveShadow = this.swatchBack.receiveShadow = true;
		this.swatchGroup.add( this.swatchFront, this.swatchBack );
		this.swatchGroup.position.copy( BAND_CENTER );

		const floor = new THREE.Mesh( new THREE.CircleGeometry( 8, 96 ), this.floorMaterial );
		floor.rotation.x = - Math.PI / 2;
		floor.position.y = - 0.30;
		floor.receiveShadow = true;
		this.floor = floor;

		scene.add( this.worn, this.swatchGroup, floor );
		this.applyShape();
		this.applyKeyLight();

		this.resizeObserver = new ResizeObserver( () => this.resize() );
		this.resizeObserver.observe( this.container );
		this.resize();

		this.hdrLoader = new HDRLoader();
		this._loop = this._loop.bind( this );
		this.renderer.setAnimationLoop( this._loop );

	}

	on( fn ) {

		this.listeners.add( fn );
		return () => this.listeners.delete( fn );

	}

	emit( what ) {

		for ( const fn of this.listeners ) fn( what );

	}

	setCameraSpherical( azDeg, elDeg, dist ) {

		const az = azDeg * Math.PI / 180, el = elDeg * Math.PI / 180;
		this.camera.position.set(
			BAND_CENTER.x + dist * Math.sin( az ) * Math.cos( el ),
			BAND_CENTER.y + dist * Math.sin( el ),
			BAND_CENTER.z + dist * Math.cos( az ) * Math.cos( el ),
		);
		this.camera.lookAt( BAND_CENTER );
		if ( this.controls ) {

			this.controls.target.copy( BAND_CENTER );
			this.controls.update();

		}

	}

	getCameraSpherical() {

		const v = this.camera.position.clone().sub( this.controls.target );
		const dist = v.length();
		return {
			azimuth: Math.atan2( v.x, v.z ) * 180 / Math.PI,
			elevation: Math.asin( v.y / dist ) * 180 / Math.PI,
			distance: dist,
		};

	}

	resize() {

		const w = Math.max( 1, this.container.clientWidth ), h = Math.max( 1, this.container.clientHeight );
		this.renderer.setSize( w, h, false );
		this.camera.aspect = w / h;
		this.camera.updateProjectionMatrix();
		this.emit( 'resize' );

	}

	set( key, value ) {

		this.state[ key ] = value;
		switch ( key ) {

			case 'shape': this.applyShape(); break;
			case 'exposure': this.renderer.toneMappingExposure = value; break;
			case 'env': this.setEnvironment( value ); break;
			case 'envRotation': this.applyEnvParams(); this.applyKeyLight(); break;
			case 'envIntensity':
			case 'background': this.applyEnvParams(); break;
			case 'stretch': this.setStrain( value ); break;
			case 'keyOn': case 'keyAzimuth': case 'keyElevation': case 'keyLux': case 'keySize': this.applyKeyLight(); break;
			case 'orbitCamera': this.controls.autoRotate = value; break;

		}
		this.emit( key );

	}

	applyShape() {

		const ring = this.state.shape === 'ring';
		this.worn.visible = ring;
		this.swatchGroup.visible = ! ring;
		this.floor.visible = true;

	}

	applyKeyLight() {

		const s = this.state;
		// the key light belongs to the light rig: rotating the environment rotates it too
		const az = ( s.keyAzimuth + s.envRotation ) * Math.PI / 180, el = s.keyElevation * Math.PI / 180;
		const d = 1.4;
		this.key.position.set( Math.sin( az ) * Math.cos( el ) * d, BAND_CENTER.y + Math.sin( el ) * d, Math.cos( az ) * Math.cos( el ) * d );
		this.key.visible = s.keyOn;
		// candela from target illuminance (lux-like units relative to the HDR radiance scale)
		this.key.intensity = s.keyOn ? s.keyLux * d * d * Math.PI : 0;
		this.key.radius = s.keySize;
		this.key.shadow.radius = 2 + s.keySize * 60;
		this.emit( 'light' );

	}

	applyEnvParams() {

		const s = this.state;
		const rot = s.envRotation * Math.PI / 180;
		this.scene.environmentRotation.set( 0, rot, 0 );
		this.scene.backgroundRotation.set( 0, rot, 0 );
		this.scene.environmentIntensity = s.envIntensity;
		if ( s.background === 'environment' && this.envTexture ) {

			this.scene.background = this.envTexture;
			this.scene.backgroundBlurriness = 0.35;
			this.scene.backgroundIntensity = s.envIntensity;
			this.renderer.setClearAlpha( 1 );

		} else if ( s.background === 'transparent' ) {

			this.scene.background = null;
			this.renderer.setClearColor( 0x000000, 0 );

		} else {

			this.scene.background = this.studioColor;

		}
		this.emit( 'environment' );

	}

	async loadEnvironment( id ) {

		if ( this.envCache.has( id ) ) return this.envCache.get( id );
		const def = ENVIRONMENTS.find( ( e ) => e.id === id );
		let tex;
		if ( def.kind === 'procedural' ) {

			const { data, width, height } = generateEnvironment( id, 1024, 512 );
			tex = new THREE.DataTexture( data, width, height, THREE.RGBAFormat, THREE.FloatType );
			tex.magFilter = THREE.LinearFilter;
			tex.minFilter = THREE.LinearFilter;
			tex.generateMipmaps = false;
			tex.needsUpdate = true;

		} else {

			// HDRIs are published as gzip + base64 text (artifact hosts only serve web media types)
			const res = await fetch( `${def.url}.txt` );
			if ( ! res.ok ) throw new Error( `Lighting file missing: ${def.url}` );
			const b64 = ( await res.text() ).trim();
			const bin = atob( b64 );
			const bytes = new Uint8Array( bin.length );
			for ( let i = 0; i < bin.length; i ++ ) bytes[ i ] = bin.charCodeAt( i );
			const hdr = this.hdrLoader.parse( gunzipSync( bytes ).buffer );
			tex = new THREE.DataTexture( hdr.data, hdr.width, hdr.height, THREE.RGBAFormat, hdr.type );
			tex.flipY = true;
			tex.magFilter = THREE.LinearFilter;
			tex.minFilter = THREE.LinearFilter;
			tex.generateMipmaps = false;
			tex.needsUpdate = true;

		}
		tex.mapping = THREE.EquirectangularReflectionMapping;
		tex.colorSpace = THREE.LinearSRGBColorSpace;
		tex.userData.envId = id;
		this.envCache.set( id, tex );
		return tex;

	}

	async setEnvironment( id ) {

		this.state.env = id;
		this.onStatus( 'Loading lighting…' );
		const tex = await this.loadEnvironment( id );
		if ( this.state.env !== id ) return;
		this.envTexture = tex;
		this.scene.environment = tex;
		const def = ENVIRONMENTS.find( ( e ) => e.id === id );
		this.applyEnvParams();
		this.onStatus( '' );
		this.emit( 'environment' );
		return def;

	}

	// Approaches provide the band material(s) and optionally take over rendering.
	setBandMaterial( material ) {

		this.ringMesh.material = material;
		this.swatchFront.material = material;

	}

	setApproach( approach ) {

		if ( this.approach && this.approach.deactivate ) this.approach.deactivate( this );
		this.approach = approach;
		if ( approach && approach.activate ) approach.activate( this );
		this.emit( 'approach' );

	}

	updateBehaviours( dt ) {

		const s = this.state;
		this.time += dt;
		let lightMoved = false;
		if ( s.orbitLight ) {

			s.keyAzimuth = ( ( s.keyAzimuth + dt * 24 + 180 ) % 360 ) - 180;
			lightMoved = true;

		}
		if ( s.spinEnv ) {

			s.envRotation = ( s.envRotation + dt * 14 ) % 360;
			this.applyEnvParams();
			lightMoved = true;

		}
		if ( lightMoved ) this.applyKeyLight();
		const breath = s.breathe ? s.breatheAmount * ( 0.5 - 0.5 * Math.cos( 2 * Math.PI * this.time / 4.2 ) ) : 0;
		this.applyStrain( s.stretch + breath );
		if ( s.shape === 'swatch' && s.flex ) {

			this.flexTime = ( this.flexTime || 0 ) + dt;
			this.swatch.update( this.flexTime, { bend: 10, twist: 1.1, wave: 7 } );

		}

	}

	_loop() {

		this.timer.update();
		const dt = Math.min( 0.05, this.timer.getDelta() );
		if ( this.paused ) return;
		const animate = ! this.approach || this.approach.allowsAnimation !== false;
		if ( animate ) this.updateBehaviours( dt );
		this.controls.update();
		if ( this.approach && this.approach.beforeRender ) this.approach.beforeRender( this, dt );
		if ( this.approach && this.approach.render ) this.approach.render( this, dt );
		else this.renderer.render( this.scene, this.camera );
		this.emit( 'frame' );

	}

	applyStrain( strain ) {

		this.strain = strain;
		const k = 1 + strain;
		this.worn.scale.set( k, 1, k );
		this.swatchGroup.scale.set( k, 1, 1 );

	}

	setStrain( strain ) {

		this.state.stretch = strain;
		this.applyStrain( strain );
		this.emit( 'stretch' );

	}

	saveState() {

		return {
			state: { ...this.state },
			position: this.camera.position.clone(),
			target: this.controls.target.clone(),
			fov: this.camera.fov,
		};

	}

	async restoreState( saved ) {

		const prevEnv = this.state.env;
		Object.assign( this.state, saved.state );
		if ( prevEnv !== saved.state.env ) await this.setEnvironment( saved.state.env );
		this.applyEnvParams();
		this.applyKeyLight();
		this.applyStrain( saved.state.stretch );
		this.camera.fov = saved.fov;
		this.camera.position.copy( saved.position );
		this.controls.target.copy( saved.target );
		this.camera.updateProjectionMatrix();
		this.controls.update();
		this.emit( 'restore' );

	}

	_withSize( width, height, fn ) {

		const r = this.renderer;
		const prevPR = r.getPixelRatio();
		const prevSize = r.getSize( new THREE.Vector2() );
		const prevAspect = this.camera.aspect;
		r.setPixelRatio( 1 );
		r.setSize( width, height, false );
		this.camera.aspect = width / height;
		this.camera.updateProjectionMatrix();
		const done = () => {

			r.setPixelRatio( prevPR );
			r.setSize( prevSize.x, prevSize.y, false );
			this.camera.aspect = prevAspect;
			this.camera.updateProjectionMatrix();

		};
		return Promise.resolve().then( fn ).finally( done );

	}

	// Render one frame at a fixed resolution: PNG blob + labels computed at that resolution.
	capture( width, height, { samples = 64 } = {} ) {

		return this._withSize( width, height, async () => {

			this.camera.updateMatrixWorld();
			if ( this.approach && this.approach.renderForCapture ) await this.approach.renderForCapture( this, { samples } );
			else this.renderer.render( this.scene, this.camera );
			const meta = this.metadata();
			const blob = await new Promise( ( res ) => this.canvas.toBlob( res, 'image/png' ) );
			return { blob, meta };

		} );

	}

	// Binary band mask (band = white) rendered with flat materials.
	captureMask( width, height ) {

		const white = this._maskWhite || ( this._maskWhite = new THREE.MeshBasicMaterial( { color: 0xffffff } ) );
		const black = this._maskBlack || ( this._maskBlack = new THREE.MeshBasicMaterial( { color: 0x000000 } ) );
		const swaps = [ [ this.ringMesh, white ], [ this.swatchFront, white ], [ this.swatchBack, white ], [ this.formMesh, black ], [ this.floor, black ] ];
		return this._withSize( width, height, async () => {

			const saved = swaps.map( ( [ m ] ) => m.material );
			const bg = this.scene.background, tm = this.renderer.toneMapping;
			swaps.forEach( ( [ m, mat ] ) => {

				m.material = mat;

			} );
			this.scene.background = new THREE.Color( 0x000000 );
			this.renderer.toneMapping = THREE.NoToneMapping;
			this.renderer.setRenderTarget( null );
			this.renderer.render( this.scene, this.camera );
			const blob = await new Promise( ( res ) => this.canvas.toBlob( res, 'image/png' ) );
			swaps.forEach( ( [ m ], i ) => {

				m.material = saved[ i ];

			} );
			this.scene.background = bg;
			this.renderer.toneMapping = tm;
			return blob;

		} );

	}

	metadata() {

		const cam = this.camera;
		const sph = this.getCameraSpherical();
		const w = this.renderer.domElement.width, h = this.renderer.domElement.height;
		const fy = 0.5 * h / Math.tan( cam.fov * Math.PI / 360 );
		cam.updateMatrixWorld();
		// row-major nested 4x4 lists (same layout as the Blender generator)
		const rows = ( m ) => [ 0, 1, 2, 3 ].map( ( r ) => [ 0, 1, 2, 3 ].map( ( c ) => m.elements[ c * 4 + r ] ) );
		return {
			camera: {
				position: cam.position.toArray(),
				quaternion: cam.quaternion.toArray(),
				target: this.controls.target.toArray(),
				fov_y_deg: cam.fov,
				azimuth_deg: sph.azimuth,
				elevation_deg: sph.elevation,
				distance_m: sph.distance,
				camera_to_world: rows( cam.matrixWorld ),
				world_to_camera: rows( cam.matrixWorldInverse ),
				projection: rows( cam.projectionMatrix ),
				intrinsics_px: { fx: fy, fy, cx: w / 2, cy: h / 2 },
			},
			lighting: {
				environment: this.state.env,
				environment_rotation_deg: this.state.envRotation,
				environment_intensity: this.state.envIntensity,
				key_light: this.state.keyOn ? {
					position: this.key.position.toArray(),
					azimuth_deg: this.state.keyAzimuth,
					world_azimuth_deg: ( this.state.keyAzimuth + this.state.envRotation ) % 360,
					elevation_deg: this.state.keyElevation,
					illuminance: this.state.keyLux,
					radius_m: this.state.keySize,
				} : null,
				exposure: this.state.exposure,
				tone_mapping: 'Khronos PBR Neutral',
			},
			geometry: { shape: this.state.shape, strain: this.strain, brick_pitch_mm: this.brickPitch },
		};

	}

}
