// Approach 5 — Blender Cycles: scrubbable viewer for the pre-rendered frame sets.
import { segmentedControl, rangeControl, selectControl, buttonControl, el } from '../ui/controls.js';

const SETS = [
	{ value: 'grid', label: 'Orbit × light' },
	{ value: 'envs', label: 'Environments' },
	{ value: 'macro', label: 'Macro' },
	{ value: 'stretch', label: 'Stretch' },
];

const ENV_LABELS = {
	studio: 'Softbox studio', darkroom: 'Flashlight (dark room)', neon: 'Neon strips',
	sunset: 'Sunset', overcast: 'Overcast city', sun: 'Hard midday sun',
};

export function createCyclesApproach( { base = 'cycles/' } = {} ) {

	let manifest = null;
	let host = null, img = null, caption = null, panel = null;
	const state = { set: 'grid', cam: 4, light: 0, env: 'studio', envCam: 2, macro: 0, stretch: 0 };
	const cache = new Map();
	let playing = null, playTimer = null;
	const ui = {};

	function frameKey() {

		switch ( state.set ) {

			case 'grid': return `c${String( state.cam ).padStart( 2, '0' )}_l${state.light}`;
			case 'envs': return `${state.env}_c${String( state.envCam ).padStart( 2, '0' )}`;
			case 'macro': return `l${String( state.macro ).padStart( 2, '0' )}`;
			case 'stretch': return `s${state.stretch}`;

		}

	}

	function entry() {

		return manifest && manifest[ state.set ] && manifest[ state.set ][ frameKey() ];

	}

	function load( rel ) {

		if ( cache.has( rel ) ) return cache.get( rel );
		const p = new Promise( ( resolve ) => {

			const i = new Image();
			i.decoding = 'async';
			i.onload = () => resolve( i );
			i.onerror = () => resolve( null );
			i.src = base + rel;

		} );
		cache.set( rel, p );
		return p;

	}

	async function show() {

		const e = entry();
		if ( ! e ) {

			caption.textContent = manifest ? 'Frame not rendered yet.' : 'Loading frames…';
			return;

		}
		const key = frameKey();
		const i = await load( e.file );
		if ( frameKey() !== key || ! i ) return;
		img.src = i.src;
		const parts = [];
		if ( e.environment ) parts.push( ENV_LABELS[ e.environment ] || e.environment );
		if ( e.camera_azimuth != null ) parts.push( `camera ${e.camera_azimuth}°` );
		if ( e.light_rotation != null ) parts.push( `light rig ${e.light_rotation}°` );
		if ( e.strain != null ) parts.push( `strain ${( e.strain * 100 ).toFixed( 0 )} %` );
		caption.textContent = parts.join( ' · ' );
		prefetch();

	}

	function prefetch() {

		const set = manifest && manifest[ state.set ];
		if ( ! set ) return;
		// neighbours first, then the rest of the set
		const keys = Object.keys( set );
		const cur = frameKey();
		const idx = keys.indexOf( cur );
		const order = keys.map( ( k, i ) => [ k, Math.abs( i - idx ) ] ).sort( ( a, b ) => a[ 1 ] - b[ 1 ] ).map( ( a ) => a[ 0 ] );
		let n = 0;
		for ( const k of order ) {

			if ( n ++ > 60 ) break;
			load( set[ k ].file );

		}

	}

	function stop() {

		clearInterval( playTimer );
		playTimer = null;
		playing = null;
		for ( const b of Object.values( ui.play || {} ) ) b.el.classList.remove( 'is-on' );

	}

	function play( kind ) {

		if ( playing === kind ) {

			stop();
			return;

		}
		stop();
		playing = kind;
		ui.play[ kind ].el.classList.add( 'is-on' );
		playTimer = setInterval( () => {

			if ( kind === 'orbit' ) {

				if ( state.set === 'grid' ) state.cam = ( state.cam + 1 ) % 24;
				if ( state.set === 'envs' ) state.envCam = ( state.envCam + 1 ) % 12;

			} else if ( kind === 'light' ) {

				if ( state.set === 'grid' ) state.light = ( state.light + 1 ) % 6;
				if ( state.set === 'macro' ) state.macro = ( state.macro + 1 ) % 24;

			} else if ( kind === 'breathe' ) {

				const seq = [ 0, 1, 2, 3, 4, 3, 2, 1 ];
				ui.breatheStep = ( ( ui.breatheStep || 0 ) + 1 ) % seq.length;
				state.stretch = seq[ ui.breatheStep ];

			}
			syncControls();
			show();

		}, kind === 'light' && state.set === 'grid' ? 600 : 160 );

	}

	function syncControls() {

		ui.cam && ui.cam.set( state.cam );
		ui.light && ui.light.set( state.light );
		ui.envCam && ui.envCam.set( state.envCam );
		ui.macro && ui.macro.set( state.macro );
		ui.stretch && ui.stretch.set( state.stretch );

	}

	function buildPanel() {

		panel.replaceChildren();
		ui.play = {};
		panel.append( segmentedControl( { label: 'Frame set', options: SETS, value: state.set, onChange: ( v ) => {

			stop();
			state.set = v;
			buildPanel();
			show();

		} } ).el );
		const row = el( 'div', 'btn-row' );
		if ( state.set === 'grid' ) {

			ui.cam = rangeControl( { label: 'Camera azimuth', min: 0, max: 23, step: 1, value: state.cam, format: ( v ) => `${v * 15}°`, onChange: ( v ) => {

				state.cam = v; show();

			} } );
			ui.light = rangeControl( { label: 'Light rig rotation', min: 0, max: 5, step: 1, value: state.light, format: ( v ) => `${v * 60}°`, onChange: ( v ) => {

				state.light = v; show();

			} } );
			panel.append( ui.cam.el, ui.light.el );
			ui.play.orbit = buttonControl( { label: 'Orbit camera', onClick: () => play( 'orbit' ) } );
			ui.play.light = buttonControl( { label: 'Rotate light', onClick: () => play( 'light' ) } );
			row.append( ui.play.orbit.el, ui.play.light.el );

		} else if ( state.set === 'envs' ) {

			panel.append( selectControl( { label: 'Environment', value: state.env, options: Object.entries( ENV_LABELS ).map( ( [ value, label ] ) => ( { value, label } ) ), onChange: ( v ) => {

				state.env = v; show();

			} } ).el );
			ui.envCam = rangeControl( { label: 'Camera azimuth', min: 0, max: 11, step: 1, value: state.envCam, format: ( v ) => `${v * 30}°`, onChange: ( v ) => {

				state.envCam = v; show();

			} } );
			panel.append( ui.envCam.el );
			ui.play.orbit = buttonControl( { label: 'Orbit camera', onClick: () => play( 'orbit' ) } );
			row.append( ui.play.orbit.el );

		} else if ( state.set === 'macro' ) {

			ui.macro = rangeControl( { label: 'Light rig rotation', min: 0, max: 23, step: 1, value: state.macro, format: ( v ) => `${v * 15}°`, onChange: ( v ) => {

				state.macro = v; show();

			} } );
			panel.append( ui.macro.el );
			ui.play.light = buttonControl( { label: 'Rotate light', onClick: () => play( 'light' ) } );
			row.append( ui.play.light.el );

		} else {

			ui.stretch = rangeControl( { label: 'Knit strain', min: 0, max: 4, step: 1, value: state.stretch, format: ( v ) => `${v * 3} %`, onChange: ( v ) => {

				state.stretch = v; show();

			} } );
			panel.append( ui.stretch.el );
			ui.play.breathe = buttonControl( { label: 'Breathe', onClick: () => play( 'breathe' ) } );
			row.append( ui.play.breathe.el );

		}
		panel.append( row );
		const note = el( 'p', 'panel-note', 'Drag the image: sideways orbits the camera, up and down turns the light rig.' );
		panel.append( note );

	}

	function attachDrag() {

		let start = null;
		img.addEventListener( 'pointerdown', ( e ) => {

			start = { x: e.clientX, y: e.clientY, cam: state.cam, envCam: state.envCam, light: state.light, macro: state.macro };
			img.setPointerCapture( e.pointerId );
			stop();

		} );
		img.addEventListener( 'pointermove', ( e ) => {

			if ( ! start ) return;
			const dx = Math.round( ( e.clientX - start.x ) / 18 ), dy = Math.round( ( e.clientY - start.y ) / 40 );
			if ( state.set === 'grid' ) {

				state.cam = ( ( start.cam - dx ) % 24 + 24 ) % 24;
				state.light = ( ( start.light + dy ) % 6 + 6 ) % 6;

			} else if ( state.set === 'envs' ) state.envCam = ( ( start.envCam - Math.round( dx / 1.5 ) ) % 12 + 12 ) % 12;
			else if ( state.set === 'macro' ) state.macro = ( ( start.macro - dx ) % 24 + 24 ) % 24;
			syncControls();
			show();

		} );
		const end = () => {

			start = null;

		};
		img.addEventListener( 'pointerup', end );
		img.addEventListener( 'pointercancel', end );

	}

	return {
		id: 'cycles',
		isFrameViewer: true,
		mount( stage, panelHost ) {

			host = el( 'figure', 'frames' );
			img = document.createElement( 'img' );
			img.alt = 'Cycles render of the band';
			img.draggable = false;
			caption = el( 'figcaption', 'frames-caption', 'Loading frames…' );
			host.append( img, caption );
			stage.append( host );
			panel = panelHost;
			attachDrag();
			fetch( base + 'manifest.json' ).then( ( r ) => r.ok ? r.json() : null ).then( ( m ) => {

				manifest = m;
				show();

			} ).catch( () => {

				caption.textContent = 'Frames are not available in this copy of the page.';

			} );

		},
		activate() {

			host.hidden = false;
			buildPanel();
			show();

		},
		deactivate() {

			stop();
			host.hidden = true;

		},
		currentSet() {

			return manifest ? { name: state.set, frames: manifest[ state.set ] || {} } : null;

		},
		base,
	};

}
