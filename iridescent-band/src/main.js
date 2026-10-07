// Iridescent Band Lab: page wiring.
import { Viewer, ENVIRONMENTS } from './core/viewer.js';
import { createBandTextures } from './core/maps.js';
import { exportDataset, saveFile, zipRemoteFiles } from './core/dataset.js';
import { createPhysicalApproach } from './approaches/a1-physical.js';
import { createSpectralApproach } from './approaches/a2-spectral.js';
import { createDiffractionApproach } from './approaches/a3-diffraction.js';
import { createPathTracerApproach } from './approaches/a4-pathtracer.js';
import { createCyclesApproach } from './approaches/a5-cycles.js';
import { APPROACHES, COMPARISON } from './ui/content.js';
import { renderHueChart } from './ui/huechart.js';
import { rangeControl, selectControl, toggleControl, segmentedControl, buttonControl, buildControl, el } from './ui/controls.js';

const $ = ( id ) => document.getElementById( id );
const reduceMotion = window.matchMedia && window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches;
const byId = Object.fromEntries( APPROACHES.map( ( a ) => [ a.id, a ] ) );
const lab = { ready: false };
window.__lab = lab;

// ------------------------------------------------------------------ static content

renderHueChart( $( 'hue-chart' ) );

// the photo crop is optional (not part of the repository): hide its figure when it is missing
const refImg = document.querySelector( '.evidence img' );
if ( refImg ) {

	const hideRef = () => {

		refImg.closest( 'figure' ).hidden = true;

	};
	refImg.addEventListener( 'error', hideRef );
	if ( refImg.complete && refImg.naturalWidth === 0 ) hideRef();

}

const tabs = {};
for ( const a of APPROACHES ) {

	const b = document.createElement( 'button' );
	b.className = 'tab';
	b.type = 'button';
	b.setAttribute( 'role', 'tab' );
	b.setAttribute( 'aria-selected', 'false' );
	b.setAttribute( 'aria-controls', 'stage' );
	b.id = `tab-${a.id}`;
	const top = el( 'span', 'tab-top' );
	top.append( el( 'span', 'tab-num', String( a.num ) ), el( 'span', 'tab-name', a.name ) );
	b.append( top, el( 'span', `chip ${a.kindTone}`, a.kind ) );
	b.addEventListener( 'click', () => selectApproach( a.id ) );
	b.addEventListener( 'keydown', ( e ) => {

		if ( e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' ) return;
		const i = APPROACHES.indexOf( a ) + ( e.key === 'ArrowRight' ? 1 : - 1 );
		const next = APPROACHES[ ( i + APPROACHES.length ) % APPROACHES.length ];
		selectApproach( next.id );
		tabs[ next.id ].focus();

	} );
	$( 'tabs' ).append( b );
	tabs[ a.id ] = b;

}

function renderCard( id ) {

	const a = byId[ id ];
	const card = $( 'card' );
	card.replaceChildren();
	const head = el( 'div', 'card-head' );
	head.append( el( 'span', `chip ${a.kindTone}`, `${a.num} · ${a.kind}` ), el( 'h3', null, a.title ), el( 'p', 'speed', a.speed ) );
	const dl = document.createElement( 'dl' );
	for ( const [ k, label ] of [ [ 'technique', 'Technique' ], [ 'physics', 'Physics' ], [ 'strengths', 'Strengths' ], [ 'limits', 'Limits' ], [ 'useFor', 'Use it for' ] ] ) {

		dl.append( el( 'dt', null, label ), el( 'dd', null, a[ k ] ) );

	}
	card.append( head, dl );

}

function buildMatrix() {

	const t = $( 'matrix' );
	const head = t.createTHead().insertRow();
	head.append( el( 'th', null, '' ) );
	COMPARISON.columns.forEach( ( c, i ) => {

		const th = el( 'th', null, `${i + 1} · ${c}` );
		th.dataset.col = i;
		th.scope = 'col';
		head.append( th );

	} );
	const body = t.createTBody();
	for ( const row of COMPARISON.rows ) {

		const tr = body.insertRow();
		const th = el( 'th', null, row.label );
		th.scope = 'row';
		tr.append( th );
		row.values.forEach( ( v, i ) => {

			const td = tr.insertCell();
			td.dataset.col = i;
			if ( row.rating ) {

				const dots = el( 'span', 'dots' );
				dots.setAttribute( 'aria-hidden', 'true' );
				for ( let k = 0; k < 3; k ++ ) dots.append( el( 'i', k < row.rating[ i ] ? 'on' : '' ) );
				td.append( dots );

			}
			td.append( document.createTextNode( v ) );

		} );

	}

}
buildMatrix();

function highlightColumn( id ) {

	const col = String( APPROACHES.findIndex( ( a ) => a.id === id ) );
	for ( const c of $( 'matrix' ).querySelectorAll( '[data-col]' ) ) c.classList.toggle( 'is-active', c.dataset.col === col );

}

// ------------------------------------------------------------------ viewer

const loading = $( 'loading' );
const setLoading = ( text ) => {

	if ( text ) loading.textContent = text;
	loading.hidden = ! text;

};

const viewer = new Viewer( $( 'viewport' ), { onStatus: ( t ) => {

	if ( lab.ready ) setLoading( t );

} } );
let webgl = true;
try {

	viewer.init();

} catch ( e ) {

	webgl = false;
	setLoading( 'WebGL 2 is not available in this browser, so the live approaches cannot run. The pre-rendered Cycles frames (tab 5) still work.' );

}

const cycles = createCyclesApproach();
cycles.mount( $( 'stage' ), $( 'panel-frames' ) );
cycles.deactivate();

const approaches = { cycles };
let activeId = null;

const lowEnd = ( navigator.deviceMemory && navigator.deviceMemory <= 4 ) || /Android|iPhone|iPad|Mobile/i.test( navigator.userAgent );

if ( webgl ) {

	await viewer.setEnvironment( 'studio' );
	const textures = await createBandTextures( viewer.renderer, { brickPitch: viewer.brickPitch, quality: lowEnd ? 'low' : 'high' } );
	const ctx = { textures, viewer };
	approaches.physical = createPhysicalApproach( ctx );
	approaches.spectral = createSpectralApproach( ctx );
	approaches.diffraction = createDiffractionApproach( ctx );
	approaches.pathtracer = createPathTracerApproach( ctx );

}

// ------------------------------------------------------------------ shared controls

const controls = {};
const flagButtons = {};

function setFlag( key, value ) {

	viewer.set( key, value );
	if ( controls[ key ] ) controls[ key ].set( value );
	if ( flagButtons[ key ] ) flagButtons[ key ].el.classList.toggle( 'is-on', value );

}

function envDefaults( id ) {

	const env = ENVIRONMENTS.find( ( e ) => e.id === id );
	const k = env.key
		? { keyOn: true, keyLux: env.keyLux, keyAzimuth: env.keyAzimuth ?? viewer.state.keyAzimuth, keyElevation: env.keyElevation ?? viewer.state.keyElevation, keySize: env.keySize ?? viewer.state.keySize }
		: { keyOn: false };
	for ( const [ key, v ] of Object.entries( k ) ) {

		viewer.state[ key ] = v;
		if ( controls[ key ] ) controls[ key ].set( v );

	}
	viewer.applyKeyLight();

}

function buildLighting() {

	const p = $( 'panel-lighting' );
	const s = viewer.state;
	controls.env = selectControl( { id: 'env', label: 'Environment', value: s.env, options: ENVIRONMENTS.map( ( e ) => ( { value: e.id, label: e.label } ) ), onChange: ( v ) => {

		viewer.set( 'env', v );
		envDefaults( v );

	} } );
	controls.envRotation = rangeControl( { id: 'env-rot', label: 'Light rig rotation', min: 0, max: 360, step: 1, value: s.envRotation, unit: '°', onChange: ( v ) => viewer.set( 'envRotation', v ) } );
	controls.envIntensity = rangeControl( { id: 'env-int', label: 'Environment intensity', min: 0.1, max: 2.5, step: 0.05, value: s.envIntensity, format: ( v ) => `× ${v.toFixed( 2 )}`, onChange: ( v ) => viewer.set( 'envIntensity', v ) } );
	controls.keyOn = toggleControl( { id: 'key-on', label: 'Key spot light', checked: s.keyOn, onChange: ( v ) => viewer.set( 'keyOn', v ) } );
	controls.keyAzimuth = rangeControl( { id: 'key-az', label: 'Key azimuth (in the rig)', min: - 180, max: 180, step: 1, value: s.keyAzimuth, unit: '°', onChange: ( v ) => viewer.set( 'keyAzimuth', v ) } );
	controls.keyElevation = rangeControl( { id: 'key-el', label: 'Key elevation', min: - 30, max: 80, step: 1, value: s.keyElevation, unit: '°', onChange: ( v ) => viewer.set( 'keyElevation', v ) } );
	controls.keyLux = rangeControl( { id: 'key-lux', label: 'Key intensity', min: 0, max: 3, step: 0.01, value: s.keyLux, onChange: ( v ) => viewer.set( 'keyLux', v ) } );
	controls.keySize = rangeControl( { id: 'key-size', label: 'Key size (soft ↔ point)', min: 0.002, max: 0.3, step: 0.001, value: s.keySize, format: ( v ) => `${( v * 100 ).toFixed( 1 )} cm`, onChange: ( v ) => viewer.set( 'keySize', v ) } );
	controls.exposure = rangeControl( { id: 'exposure', label: 'Exposure', min: 0.3, max: 2.5, step: 0.01, value: s.exposure, format: ( v ) => `× ${v.toFixed( 2 )}`, onChange: ( v ) => viewer.set( 'exposure', v ) } );
	controls.background = selectControl( { id: 'bg', label: 'Background', value: s.background, options: [
		{ value: 'studio', label: 'Dark studio backdrop' }, { value: 'environment', label: 'Environment (blurred)' }, { value: 'transparent', label: 'Transparent (for compositing)' },
	], onChange: ( v ) => viewer.set( 'background', v ) } );
	p.append( controls.env.el, controls.envRotation.el, controls.envIntensity.el, controls.keyOn.el, controls.keyAzimuth.el, controls.keyElevation.el, controls.keyLux.el, controls.keySize.el, controls.exposure.el, controls.background.el );

}

const MOTION_FLAGS = [
	[ 'spinEnv', 'Rotate light rig' ],
	[ 'orbitCamera', 'Orbit camera' ],
	[ 'orbitLight', 'Orbit key light' ],
	[ 'breathe', 'Breathing stretch' ],
	[ 'flex', 'Flex the swatch' ],
];

function buildMotion() {

	const p = $( 'panel-motion' );
	const s = viewer.state;
	controls.shape = segmentedControl( { label: 'Shape', name: 'shape', value: s.shape, options: [ { value: 'ring', label: 'Worn on form' }, { value: 'swatch', label: 'Flexing swatch' } ], onChange: ( v ) => {

		viewer.set( 'shape', v );
		if ( v === 'swatch' ) viewer.setCameraSpherical( 8, 6, 0.26 );
		else viewer.setCameraSpherical( 24, 5, photoDistance() );

	} } );
	const grid = el( 'div', 'toggle-grid' );
	for ( const [ key, label ] of MOTION_FLAGS ) {

		controls[ key ] = toggleControl( { id: `flag-${key}`, label, checked: s[ key ], onChange: ( v ) => setFlag( key, v ) } );
		grid.append( controls[ key ].el );

	}
	controls.stretch = rangeControl( { id: 'stretch', label: 'Static knit strain', min: 0, max: 0.15, step: 0.005, value: s.stretch, format: ( v ) => `${( v * 100 ).toFixed( 1 )} %`, onChange: ( v ) => viewer.set( 'stretch', v ) } );
	const row = el( 'div', 'btn-row' );
	row.append(
		buttonControl( { label: 'Match photo view', onClick: matchPhoto } ).el,
		buttonControl( { label: 'Front view', onClick: () => viewer.setCameraSpherical( 0, 4, 0.42 ) } ).el,
		buttonControl( { label: 'Macro', onClick: () => viewer.setCameraSpherical( 24, 3, 0.11 ) } ).el,
	);
	controls.motionNote = el( 'p', 'panel-note', '' );
	p.append( controls.shape.el, grid, controls.stretch.el, row, controls.motionNote );

}

function matchPhoto() {

	for ( const key of [ 'spinEnv', 'orbitCamera', 'orbitLight', 'breathe' ] ) setFlag( key, false );
	viewer.set( 'shape', 'ring' );
	controls.shape.set( 'ring' );
	viewer.set( 'env', 'studio' );
	controls.env.set( 'studio' );
	envDefaults( 'studio' );
	viewer.set( 'envRotation', 0 );
	controls.envRotation.set( 0 );
	viewer.set( 'stretch', 0 );
	controls.stretch.set( 0 );
	viewer.camera.fov = 28;
	viewer.camera.updateProjectionMatrix();
	viewer.setCameraSpherical( 24, 5, photoDistance() );

}

// back off on portrait stages so the whole front of the band stays in frame
function photoDistance() {

	return viewer.camera.aspect < 1.25 ? 0.6 : 0.46;

}

function buildStageActions() {

	const host = $( 'stage-actions' );
	for ( const [ key, label ] of [ [ 'spinEnv', 'Rotate light' ], [ 'orbitCamera', 'Orbit' ], [ 'breathe', 'Breathe' ] ] ) {

		const b = buttonControl( { label, onClick: () => setFlag( key, ! viewer.state[ key ] ) } );
		b.el.setAttribute( 'aria-pressed', 'false' );
		flagButtons[ key ] = b;
		host.append( b.el );

	}
	const shapeBtn = buttonControl( { label: 'Swatch', onClick: () => {

		const next = viewer.state.shape === 'ring' ? 'swatch' : 'ring';
		viewer.set( 'shape', next );
		controls.shape.set( next );
		shapeBtn.setLabel( next === 'ring' ? 'Swatch' : 'Worn' );
		if ( next === 'swatch' ) viewer.setCameraSpherical( 8, 6, 0.26 );
		else viewer.setCameraSpherical( 24, 5, photoDistance() );

	} } );
	host.append( shapeBtn.el );
	controls.shapeBtn = shapeBtn;

}

function syncFlagButtons() {

	for ( const [ key, b ] of Object.entries( flagButtons ) ) {

		b.el.classList.toggle( 'is-on', !! viewer.state[ key ] );
		b.el.setAttribute( 'aria-pressed', viewer.state[ key ] ? 'true' : 'false' );

	}

}

function buildMaterial( approach ) {

	const p = $( 'panel-material' );
	p.replaceChildren();
	$( 'material-title' ).textContent = `Material · ${byId[ approach.id ].name}`;
	for ( const spec of approach.controls ) {

		const c = buildControl( { ...spec, id: `m-${approach.id}-${spec.key}` }, approach.params[ spec.key ], ( v ) => {

			const r = approach.set( spec.key, v );
			if ( r === 'refresh' ) buildMaterial( approach );

		} );
		p.append( c.el );

	}

}

// ------------------------------------------------------------------ capture

const capture = { count: 24, size: 768, camera: true, lighting: true, key: true, stretch: true, masks: true, samples: 64 };

function buildCapture() {

	const p = $( 'panel-capture' );
	p.append(
		segmentedControl( { label: 'Frames', name: 'cap-count', value: String( capture.count ), options: [ 12, 24, 48, 96 ].map( ( n ) => ( { value: String( n ), label: String( n ) } ) ), onChange: ( v ) => {

			capture.count = + v;

		} } ).el,
		segmentedControl( { label: 'Size (px, square)', name: 'cap-size', value: String( capture.size ), options: [ 512, 768, 1024 ].map( ( n ) => ( { value: String( n ), label: String( n ) } ) ), onChange: ( v ) => {

			capture.size = + v;

		} } ).el,
	);
	const grid = el( 'div', 'toggle-grid' );
	for ( const [ key, label ] of [ [ 'camera', 'Random camera' ], [ 'lighting', 'Random lighting' ], [ 'key', 'Random key light' ], [ 'stretch', 'Random stretch' ], [ 'masks', 'Band masks' ] ] ) {

		grid.append( toggleControl( { id: `cap-${key}`, label, checked: capture[ key ], onChange: ( v ) => {

			capture[ key ] = v;

		} } ).el );

	}
	p.append( grid );
	controls.capSamples = rangeControl( { id: 'cap-samples', label: 'Path-traced samples per frame', min: 16, max: 512, step: 16, value: capture.samples, onChange: ( v ) => {

		capture.samples = v;

	} } );
	p.append( controls.capSamples.el );
	const row = el( 'div', 'btn-row' );
	controls.exportBtn = buttonControl( { label: 'Export dataset (.zip)', variant: 'primary', onClick: runExport } );
	controls.snapBtn = buttonControl( { label: 'Save this view (.png)', onClick: saveView } );
	row.append( controls.exportBtn.el, controls.snapBtn.el );
	controls.capProgress = el( 'p', 'progress', '' );
	controls.capProgress.setAttribute( 'role', 'status' );
	p.append( row, controls.capProgress, el( 'p', 'panel-note', 'Each frame comes with camera intrinsics and extrinsics, the light rig, the strain and the material parameters in labels.jsonl.' ) );

}

const SAVE_ERRORS = {
	declined: 'Download cancelled.',
	too_large: 'That file is too large for this viewer. Export fewer frames or a smaller size.',
	rate_limited: 'A save prompt is already open. Finish it, then try again.',
	unavailable: 'This view cannot save files. Open the page in the Claude app or in a browser tab to export.',
};

async function deliver( filename, blob ) {

	controls.capProgress.textContent = `Handing over ${filename} (${( blob.size / 1e6 ).toFixed( 1 )} MB)…`;
	const r = await saveFile( filename, blob );
	controls.capProgress.textContent = r.ok ? `Saved ${filename}.` : ( SAVE_ERRORS[ r.code ] || SAVE_ERRORS.unavailable );
	return r;

}

let busy = false;

async function runExport() {

	const approach = approaches[ activeId ];
	if ( ! approach || approach.isFrameViewer || busy ) return;
	busy = true;
	controls.exportBtn.disable( true );
	controls.snapBtn.disable( true );
	for ( const b of Object.values( tabs ) ) b.disabled = true;
	try {

		const blob = await exportDataset( viewer, {
			approachId: activeId, approach, count: capture.count, size: capture.size, masks: capture.masks, samples: capture.samples,
			rand: { camera: capture.camera, lighting: capture.lighting, key: capture.key, stretch: capture.stretch },
			onProgress: ( i, n ) => {

				controls.capProgress.textContent = `Rendering frame ${i} of ${n}…`;

			},
		} );
		syncAllControls();
		await deliver( `band-${activeId}-${capture.count}f-${capture.size}px.zip`, blob );

	} catch ( e ) {

		controls.capProgress.textContent = `Export failed: ${e.message}`;

	} finally {

		busy = false;
		controls.exportBtn.disable( false );
		controls.snapBtn.disable( false );
		for ( const b of Object.values( tabs ) ) b.disabled = false;

	}

}

async function saveView() {

	const approach = approaches[ activeId ];
	let blob;
	if ( approach && approach.id === 'pathtracer' ) blob = await new Promise( ( r ) => viewer.canvas.toBlob( r, 'image/png' ) );
	else blob = ( await viewer.capture( viewer.canvas.width, viewer.canvas.height ) ).blob;
	await deliver( `band-${activeId}-view.png`, blob );

}

async function exportCyclesSet() {

	const set = cycles.currentSet();
	if ( ! set ) return;
	const entries = Object.entries( set.frames ).map( ( [ k, v ] ) => [ `${set.name}/${k}${v.file.slice( v.file.lastIndexOf( '.' ) )}`, v.file ] );
	cyclesProgress.textContent = `Collecting ${entries.length} frames…`;
	const blob = await zipRemoteFiles( cycles.base, entries, { 'manifest.json': JSON.stringify( { [ set.name ]: set.frames }, null, 1 ) } );
	cyclesProgress.textContent = `Handing over ${( blob.size / 1e6 ).toFixed( 1 )} MB…`;
	const r = await saveFile( `band-cycles-${set.name}.zip`, blob );
	cyclesProgress.textContent = r.ok ? `Saved band-cycles-${set.name}.zip.` : ( SAVE_ERRORS[ r.code ] || SAVE_ERRORS.unavailable );

}

let cyclesProgress;
function buildFramesFooter() {

	const g = $( 'g-frames' );
	const body = el( 'div', 'group-body' );
	const b = buttonControl( { label: 'Download this frame set (.zip)', onClick: exportCyclesSet } );
	cyclesProgress = el( 'p', 'progress', '' );
	cyclesProgress.setAttribute( 'role', 'status' );
	body.append( b.el, cyclesProgress, el( 'p', 'panel-note', 'Rendered with blender/render_sequences.py from the repository; generate_dataset.py makes randomised sets with masks and labels.' ) );
	g.append( body );

}

function syncAllControls() {

	const s = viewer.state;
	for ( const key of [ 'env', 'envRotation', 'envIntensity', 'keyOn', 'keyAzimuth', 'keyElevation', 'keyLux', 'keySize', 'exposure', 'background', 'stretch', 'shape' ] ) {

		if ( controls[ key ] ) controls[ key ].set( s[ key ] );

	}
	for ( const [ key ] of MOTION_FLAGS ) controls[ key ] && controls[ key ].set( s[ key ] );
	syncFlagButtons();

}

// ------------------------------------------------------------------ approach switching

function setLiveUI( approachId ) {

	const live = approachId !== 'cycles';
	for ( const id of [ 'g-lighting', 'g-motion', 'g-material', 'g-capture' ] ) $( id ).hidden = ! live;
	$( 'g-frames' ).hidden = live;
	$( 'viewport' ).hidden = ! live;
	$( 'stage-actions' ).hidden = ! live;
	$( 'stage-status' ).hidden = ! live;
	$( 'stage-hint' ).hidden = ! live;
	const pt = approachId === 'pathtracer';
	for ( const [ key ] of MOTION_FLAGS ) controls[ key ] && controls[ key ].disable( pt );
	for ( const b of Object.values( flagButtons ) ) b.disable( pt );
	if ( controls.shapeBtn ) controls.shapeBtn.disable( false );
	if ( controls.motionNote ) controls.motionNote.textContent = pt ? 'Animations pause while path tracing. Change the light or view and the image re-converges.' : '';
	if ( controls.capSamples ) controls.capSamples.el.hidden = ! pt;

}

function selectApproach( id ) {

	if ( busy ) return;
	if ( ! approaches[ id ] ) id = approaches.spectral ? 'spectral' : 'cycles';
	if ( id === activeId ) return;
	const prev = activeId;
	activeId = id;
	for ( const [ k, b ] of Object.entries( tabs ) ) {

		b.setAttribute( 'aria-selected', k === id ? 'true' : 'false' );
		b.tabIndex = k === id ? 0 : - 1;

	}
	renderCard( id );
	highlightColumn( id );
	try {

		history.replaceState( null, '', `#a${byId[ id ].num}` );

	} catch ( e ) { /* sandboxed history */ }

	if ( prev === 'cycles' ) cycles.deactivate();
	if ( id === 'cycles' ) {

		if ( webgl ) {

			viewer.setApproach( null );
			viewer.paused = true;

		}
		cycles.activate();

	} else {

		viewer.paused = false;
		viewer.setApproach( approaches[ id ] );
		buildMaterial( approaches[ id ] );

	}
	setLiveUI( id );

}

// status pill: frame rate for live approaches, sample count for the path tracer
let frames = 0;
viewer.on( ( what ) => {

	if ( what === 'frame' ) frames ++;
	if ( what === 'light' || what === 'environment' ) {

		if ( controls.keyAzimuth ) controls.keyAzimuth.set( viewer.state.keyAzimuth );
		if ( controls.envRotation ) controls.envRotation.set( Math.round( viewer.state.envRotation ) );

	}

} );
setInterval( () => {

	const host = $( 'stage-status' );
	if ( ! lab.ready || activeId === 'cycles' ) {

		frames = 0;
		return;

	}
	const env = ENVIRONMENTS.find( ( e ) => e.id === viewer.state.env );
	const a = approaches[ activeId ];
	const left = activeId === 'pathtracer' ? `${a.samples} samples` : ( frames > 0 ? `${frames * 2} fps` : '< 2 fps' );
	frames = 0;
	host.replaceChildren( el( 'span', 'pill', left ), el( 'span', 'pill', env ? env.label.split( ' (' )[ 0 ] : '' ) );

}, 500 );

// pause rendering while the stage is off screen
if ( 'IntersectionObserver' in window ) {

	new IntersectionObserver( ( entries ) => {

		const visible = entries[ 0 ].isIntersecting;
		if ( activeId !== 'cycles' && webgl && ! busy ) viewer.paused = ! visible;

	} ).observe( $( 'stage' ) );

}

// ------------------------------------------------------------------ boot

if ( webgl ) {

	buildLighting();
	buildMotion();
	buildStageActions();
	buildCapture();

}
buildFramesFooter();
if ( window.innerWidth < 760 ) for ( const id of [ 'g-motion', 'g-material' ] ) $( id ).open = false;

const fromHash = ( location.hash || '' ).match( /^#a([1-5])$/ );
const initial = fromHash ? APPROACHES[ + fromHash[ 1 ] - 1 ].id : 'spectral';
selectApproach( webgl ? initial : 'cycles' );
if ( webgl && viewer.camera.aspect < 1.25 ) viewer.setCameraSpherical( 24, 5, photoDistance() );
if ( webgl && ! reduceMotion ) setFlag( 'spinEnv', true );
syncFlagButtons();
if ( webgl ) setLoading( '' );
lab.ready = true;
Object.assign( lab, { viewer, approaches, use: selectApproach, matchPhoto, setFlag } );
