// Small DOM control builders with two-way sync (control.set(value) updates without firing onChange).

let uid = 0;
const nextId = ( prefix ) => `${prefix}-${++ uid}`;

function el( tag, cls, text ) {

	const e = document.createElement( tag );
	if ( cls ) e.className = cls;
	if ( text != null ) e.textContent = text;
	return e;

}

function fmt( v, step, unit ) {

	const decimals = step >= 1 ? 0 : Math.min( 3, Math.max( 0, Math.ceil( - Math.log10( step ) ) ) );
	const s = Number( v ).toFixed( decimals );
	return unit ? `${s} ${unit}` : s;

}

export function rangeControl( { id, label, min, max, step = 0.01, value, unit = '', format, onChange } ) {

	const wrap = el( 'div', 'ctl ctl-range' );
	const inputId = id || nextId( 'rng' );
	const head = el( 'label', 'ctl-head' );
	head.htmlFor = inputId;
	const name = el( 'span', 'ctl-label', label );
	const out = el( 'output', 'ctl-value' );
	out.htmlFor = inputId;
	head.append( name, out );
	const input = document.createElement( 'input' );
	input.type = 'range';
	input.id = inputId;
	input.min = min; input.max = max; input.step = step; input.value = value;
	const show = ( v ) => {

		out.textContent = format ? format( v ) : fmt( v, step, unit );

	};
	show( value );
	input.addEventListener( 'input', () => {

		const v = parseFloat( input.value );
		show( v );
		onChange && onChange( v );

	} );
	wrap.append( head, input );
	return {
		el: wrap,
		set( v ) {

			input.value = v;
			show( v );

		},
		disable( d ) {

			input.disabled = d;
			wrap.classList.toggle( 'is-disabled', d );

		},
	};

}

export function selectControl( { id, label, options, value, onChange } ) {

	const wrap = el( 'div', 'ctl ctl-select' );
	const inputId = id || nextId( 'sel' );
	const head = el( 'label', 'ctl-head' );
	head.htmlFor = inputId;
	head.append( el( 'span', 'ctl-label', label ) );
	const select = document.createElement( 'select' );
	select.id = inputId;
	for ( const o of options ) {

		const opt = document.createElement( 'option' );
		opt.value = o.value;
		opt.textContent = o.label;
		select.append( opt );

	}
	select.value = value;
	select.addEventListener( 'change', () => onChange && onChange( select.value ) );
	wrap.append( head, select );
	return {
		el: wrap,
		set( v ) {

			select.value = v;

		},
		disable( d ) {

			select.disabled = d;
			wrap.classList.toggle( 'is-disabled', d );

		},
	};

}

export function toggleControl( { id, label, checked = false, onChange, hint } ) {

	const wrap = el( 'label', 'ctl ctl-toggle' );
	const input = document.createElement( 'input' );
	input.type = 'checkbox';
	input.setAttribute( 'role', 'switch' );
	input.id = id || nextId( 'tgl' );
	input.checked = checked;
	const track = el( 'span', 'switch' );
	track.setAttribute( 'aria-hidden', 'true' );
	const text = el( 'span', 'ctl-label', label );
	wrap.append( input, track, text );
	if ( hint ) wrap.title = hint;
	input.addEventListener( 'change', () => onChange && onChange( input.checked ) );
	return {
		el: wrap,
		set( v ) {

			input.checked = !! v;

		},
		disable( d ) {

			input.disabled = d;
			wrap.classList.toggle( 'is-disabled', d );

		},
	};

}

export function segmentedControl( { label, options, value, onChange, name } ) {

	const wrap = el( 'div', 'ctl ctl-seg' );
	const group = el( 'div', 'seg' );
	group.setAttribute( 'role', 'radiogroup' );
	const groupName = name || nextId( 'seg' );
	if ( label ) {

		const l = el( 'span', 'ctl-label', label );
		l.id = groupName + '-label';
		group.setAttribute( 'aria-labelledby', l.id );
		wrap.append( l );

	}
	const inputs = [];
	for ( const o of options ) {

		const lab = el( 'label', 'seg-item' );
		const input = document.createElement( 'input' );
		input.type = 'radio';
		input.name = groupName;
		input.id = `${groupName}-${o.value}`;
		input.value = o.value;
		input.checked = o.value === value;
		input.addEventListener( 'change', () => input.checked && onChange && onChange( o.value ) );
		lab.append( input, el( 'span', null, o.label ) );
		group.append( lab );
		inputs.push( input );

	}
	wrap.append( group );
	return {
		el: wrap,
		set( v ) {

			for ( const i of inputs ) i.checked = i.value === v;

		},
		disable( d ) {

			for ( const i of inputs ) i.disabled = d;
			wrap.classList.toggle( 'is-disabled', d );

		},
	};

}

export function buttonControl( { label, onClick, variant = 'ghost', id } ) {

	const b = el( 'button', `btn btn-${variant}`, label );
	b.type = 'button';
	if ( id ) b.id = id;
	b.addEventListener( 'click', onClick );
	return { el: b, disable( d ) {

		b.disabled = d;

	}, setLabel( t ) {

		b.textContent = t;

	} };

}

export function buildControl( spec, value, onChange ) {

	switch ( spec.type ) {

		case 'range': return rangeControl( { ...spec, value, onChange } );
		case 'select': return selectControl( { ...spec, value, onChange } );
		case 'toggle': return toggleControl( { ...spec, checked: value, onChange } );
		case 'segmented': return segmentedControl( { ...spec, value, onChange } );
		default: throw new Error( 'unknown control ' + spec.type );

	}

}

export { el };
