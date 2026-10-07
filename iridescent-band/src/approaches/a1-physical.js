// Approach 1 — stock three.js MeshPhysicalMaterial with KHR_materials_iridescence + sheen.
// Everything here maps 1:1 onto glTF 2.0 extensions, so the material exports to any glTF engine.
import * as THREE from 'three';

export function createPhysicalApproach( { textures } ) {

	const params = {
		filmIOR: 2.33,
		thickness: 111,
		spread: 10,
		baseIOR: 1.58,
		coat: 1.0,
		roughness: 1.0,
		normalStrength: 1.0,
		sheen: 0.3,
	};

	const material = new THREE.MeshPhysicalMaterial( {
		map: textures.albedo,
		normalMap: textures.normal,
		roughnessMap: textures.orm,
		roughness: params.roughness,
		aoMap: textures.orm,
		aoMapIntensity: 1,
		metalness: 0,
		ior: params.baseIOR,
		specularIntensity: 1,
		iridescence: params.coat,
		iridescenceMap: textures.irid,
		iridescenceIOR: params.filmIOR,
		iridescenceThicknessMap: textures.irid,
		iridescenceThicknessRange: [ 100, 400 ],
		sheen: params.sheen,
		sheenRoughness: 0.55,
		sheenColor: new THREE.Color( 0x9fb3a6 ),
	} );

	let strain = 0;

	function applyThickness() {

		// knit strain thins the coating (Poisson ratio ~0.45 for the elastomer carrier)
		const d = params.thickness / ( 1 + 0.45 * strain );
		const s = params.spread / 100;
		material.iridescenceThicknessRange = [ d * ( 1 - s ), d * ( 1 + s ) ];

	}
	applyThickness();

	return {
		id: 'physical',
		material,
		controls: [
			{ key: 'thickness', label: 'Film thickness', type: 'range', min: 40, max: 700, step: 1, unit: 'nm' },
			{ key: 'spread', label: 'Thickness variation', type: 'range', min: 0, max: 40, step: 1, unit: '%' },
			{ key: 'filmIOR', label: 'Film IOR', type: 'range', min: 1.2, max: 2.333, step: 0.01 },
			{ key: 'baseIOR', label: 'Base IOR', type: 'range', min: 1.3, max: 2.0, step: 0.01 },
			{ key: 'coat', label: 'Iridescence weight', type: 'range', min: 0, max: 1, step: 0.01 },
			{ key: 'roughness', label: 'Roughness scale', type: 'range', min: 0.2, max: 1.6, step: 0.01 },
			{ key: 'normalStrength', label: 'Relief (normal map)', type: 'range', min: 0, max: 2, step: 0.01 },
			{ key: 'sheen', label: 'Fabric sheen', type: 'range', min: 0, max: 1, step: 0.01 },
		],
		params,
		set( key, value ) {

			params[ key ] = value;
			switch ( key ) {

				case 'filmIOR': material.iridescenceIOR = value; break;
				case 'baseIOR': material.ior = value; break;
				case 'coat': material.iridescence = value; break;
				case 'roughness': material.roughness = value; break;
				case 'normalStrength': material.normalScale.set( value, value ); break;
				case 'sheen': material.sheen = value; break;
				default: applyThickness();

			}

		},
		activate( viewer ) {

			viewer.setBandMaterial( material );

		},
		beforeRender( viewer ) {

			if ( Math.abs( viewer.strain - strain ) > 1e-4 ) {

				strain = viewer.strain;
				applyThickness();

			}

		},
		describe() {

			return {
				model: 'three.js MeshPhysicalMaterial (glTF KHR_materials_iridescence, Belcour-Barla thin film)',
				film_ior: params.filmIOR, film_thickness_nm: params.thickness, thickness_variation_pct: params.spread,
				base_ior: params.baseIOR, iridescence: params.coat, roughness_scale: params.roughness, sheen: params.sheen,
			};

		},
	};

}
