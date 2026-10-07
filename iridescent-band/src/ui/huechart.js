// Measured colours from the reference photo, placed on the estimated surface angle.
import MEASURED from './measured.json';

const SVGNS = 'http://www.w3.org/2000/svg';

function s( tag, attrs = {}, parent ) {

	const e = document.createElementNS( SVGNS, tag );
	for ( const [ k, v ] of Object.entries( attrs ) ) e.setAttribute( k, v );
	if ( parent ) parent.appendChild( e );
	return e;

}

export function renderHueChart( host ) {

	const data = [ ...MEASURED ].sort( ( a, b ) => a.angle - b.angle );
	const W = 640, H = 128, left = 64, right = 12;
	const a0 = - 70, a1 = 40;
	const x = ( a ) => left + ( a - a0 ) / ( a1 - a0 ) * ( W - left - right );
	const svg = s( 'svg', { viewBox: `0 0 ${W} ${H}`, class: 'huechart-svg', role: 'img', 'aria-label': 'Measured lattice and brick colours of the band versus estimated surface angle' } );
	const rows = [ { key: 'lattice', label: 'Lattice', y: 10 }, { key: 'brick', label: 'Bricks', y: 50 } ];
	const rowH = 34;
	for ( const r of rows ) {

		const t = s( 'text', { x: 0, y: r.y + rowH / 2 + 4, class: 'hc-row-label' }, svg );
		t.textContent = r.label;

	}
	const tip = document.createElement( 'div' );
	tip.className = 'hc-tip';
	tip.hidden = true;
	host.style.position = 'relative';

	const bounds = data.map( ( d, i ) => {

		const prev = i > 0 ? ( data[ i - 1 ].angle + d.angle ) / 2 : d.angle - 1.5;
		const next = i < data.length - 1 ? ( data[ i + 1 ].angle + d.angle ) / 2 : d.angle + 1.5;
		return [ prev, next ];

	} );
	data.forEach( ( d, i ) => {

		const [ b0, b1 ] = bounds[ i ];
		const gx = x( b0 ), gw = Math.max( 1, x( b1 ) - x( b0 ) - 2 ); // 2px surface gap between swatches
		const g = s( 'g', { class: 'hc-col', tabindex: 0, 'aria-label': `${d.angle}°: lattice ${d.lattice}, bricks ${d.brick}` }, svg );
		for ( const r of rows ) s( 'rect', { x: gx + 1, y: r.y, width: gw, height: rowH, rx: 2, fill: d[ r.key ] }, g );
		s( 'rect', { x: gx, y: 4, width: gw + 2, height: 86, fill: 'transparent', class: 'hc-hit' }, g );
		const show = () => {

			tip.hidden = false;
			tip.replaceChildren();
			const v = document.createElement( 'strong' );
			v.textContent = `${d.angle > 0 ? '+' : ''}${d.angle.toFixed( 0 )}°`;
			const l1 = document.createElement( 'span' );
			l1.textContent = `lattice ${d.lattice}`;
			const l2 = document.createElement( 'span' );
			l2.textContent = `bricks ${d.brick}`;
			const sw = ( c ) => {

				const k = document.createElement( 'i' );
				k.style.background = c;
				return k;

			};
			l1.prepend( sw( d.lattice ) );
			l2.prepend( sw( d.brick ) );
			tip.append( v, l1, l2 );
			const rect = host.getBoundingClientRect();
			const px = ( x( d.angle ) / W ) * rect.width;
			tip.style.left = `${Math.min( rect.width - 140, Math.max( 0, px - 70 ) )}px`;
			g.classList.add( 'is-hover' );

		};
		const hide = () => {

			tip.hidden = true;
			g.classList.remove( 'is-hover' );

		};
		g.addEventListener( 'pointerenter', show );
		g.addEventListener( 'pointerleave', hide );
		g.addEventListener( 'focus', show );
		g.addEventListener( 'blur', hide );

	} );

	// axis
	s( 'line', { x1: left, x2: W - right, y1: 96, y2: 96, class: 'hc-axis' }, svg );
	for ( let a = - 60; a <= 40; a += 20 ) {

		s( 'line', { x1: x( a ), x2: x( a ), y1: 96, y2: 100, class: 'hc-axis' }, svg );
		const t = s( 'text', { x: x( a ), y: 114, class: 'hc-tick', 'text-anchor': 'middle' }, svg );
		t.textContent = `${a > 0 ? '+' : ''}${a}°`;

	}
	const cap = s( 'text', { x: W - right, y: 126, class: 'hc-tick', 'text-anchor': 'end' }, svg );
	cap.textContent = 'estimated surface angle to camera';

	host.append( svg, tip );

	// table view
	const details = document.createElement( 'details' );
	details.className = 'hc-table';
	const sum = document.createElement( 'summary' );
	sum.textContent = 'Show as table';
	const wrap = document.createElement( 'div' );
	wrap.className = 'table-scroll';
	const table = document.createElement( 'table' );
	const head = table.createTHead().insertRow();
	for ( const h of [ 'Angle', 'Lattice', 'Bricks' ] ) {

		const th = document.createElement( 'th' );
		th.textContent = h;
		head.append( th );

	}
	const body = table.createTBody();
	for ( const d of data ) {

		const r = body.insertRow();
		r.insertCell().textContent = `${d.angle.toFixed( 1 )}°`;
		r.insertCell().textContent = d.lattice;
		r.insertCell().textContent = d.brick;

	}
	wrap.append( table );
	details.append( sum, wrap );
	host.after( details );

}
