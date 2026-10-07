// Approach 3 — holographic diffraction-grating shader (real time).
//
// Alternative physical hypothesis: the colour comes from an embossed grating (holographic foil),
// not from thin-film interference. Grating equation, vectors pointing away from the surface:
//   L_t = −V_t + m·λ/Λ  (along the grating vector),  L_b = −V_b  (along the grooves)
// Environment light: each order m and wavelength bin λ_k fetches the environment from its own
// direction, so bright regions are spread into spectra (rainbow smear of softboxes and sun).
// Point/spot lights: Stam-style spectral lobe centred on u = L_t + V_t = m·λ/Λ.
import * as THREE from 'three';
import { wavelengthBins } from '../core/spectral.js';
import { injectBRDF, BAND_GLSL, BAND_SAMPLE_GLSL } from './inject.js';

const NB = 12;

const PARS = /* glsl */`
${BAND_GLSL}
uniform float uPeriod;
uniform float uEta1;
uniform float uEta2;
uniform float uF0;
uniform float uMetal;
uniform float uSigma;
uniform float uLightSize;
uniform float uOrient;
uniform float uRandomOrient;
uniform float uThin;
uniform vec3 uBinRGB[ ${NB} ];
uniform float uBinLambda[ ${NB} ];

vec3 gGrat;
vec3 gGroove;
vec3 gN;
float gPeriod;

#ifdef USE_ENVMAP
vec3 lab_envDir( const in vec3 dirView, const in float rough ) {

	vec3 w = transformDirectionByInverseViewMatrix( dirView, viewMatrix );
	return textureCubeUV( envMap, envMapRotation * w, rough ).rgb * envMapIntensity;

}

vec3 lab_order( const in float lt, const in float lb, const in float rough ) {

	float ln2 = 1.0 - lt * lt - lb * lb;
	if ( ln2 <= 0.0 ) return vec3( 0.0 ); // evanescent order
	return lab_envDir( lt * gGrat + lb * gGroove + sqrt( ln2 ) * gN, rough );

}
#endif

void RE_Direct_Diffraction( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {

	vec3 N = geometryNormal;
	vec3 V = geometryViewDir;
	vec3 L = directLight.direction;
	float NoL = saturate( dot( N, L ) );
	if ( NoL <= 0.0 ) return;
	float NoV = saturate( dot( N, V ) ) + 1e-4;
	vec3 H = normalize( L + V );
	float NoH = saturate( dot( N, H ) );
	float VoH = saturate( dot( V, H ) );
	float alpha = min( 1.0, pow2( material.roughness ) + uLightSize );
	float D = D_GGX( alpha, NoH );
	float Vis = V_GGX_SmithCorrelated( alpha, NoL, NoV );
	vec3 irradiance = NoL * directLight.color;

	float etaTot = 2.0 * ( uEta1 + uEta2 );
	vec3 F0c = mix( vec3( uF0 ), vec3( 0.91 ), uMetal );
	vec3 Fz = F_Schlick( F0c, 1.0, VoH ) * ( 1.0 - etaTot );
	vec3 Fd = F_Schlick( vec3( 0.04 ), 1.0, VoH );
	reflectedLight.directSpecular += irradiance * mix( Fd, Fz, gCoat ) * ( D * Vis );

	if ( gCoat > 0.001 ) {

		float u = dot( L, gGrat ) + dot( V, gGrat );
		float b = dot( L, gGroove ) + dot( V, gGroove );
		float sg = uSigma + uLightSize * 0.5 + material.roughness * 0.04;
		float inv = 1.0 / ( 2.0 * sg * sg );
		vec3 col = vec3( 0.0 );
		for ( int k = 0; k < ${NB}; k ++ ) {

			float q = uBinLambda[ k ] / gPeriod;
			float a1 = u - q, b1 = u + q;
			float w = uEta1 * ( exp( - ( a1 * a1 + b * b ) * inv ) + exp( - ( b1 * b1 + b * b ) * inv ) );
			if ( uEta2 > 0.0 ) {

				float a2 = u - 2.0 * q, b2 = u + 2.0 * q;
				w += uEta2 * ( exp( - ( a2 * a2 + b * b ) * inv ) + exp( - ( b2 * b2 + b * b ) * inv ) );

			}
			col += uBinRGB[ k ] * w;

		}
		// lobe normalised over projected solid angle: 1 / (2π σ²)
		reflectedLight.directSpecular += irradiance * col * ( inv / PI ) * gCoat;

	}

	float diffT = mix( max( 0.0, 1.0 - uF0 - etaTot ), 0.0, uMetal );
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor ) * mix( 1.0 - Fd.g, diffT, gCoat );

	float sheenW = ( 1.0 - gCoat ) * uSheen;
	if ( sheenW > 0.0 ) reflectedLight.directSpecular += irradiance * sheenW * uSheenColor * lab_charlieD( 0.55, NoH ) * lab_neubeltV( NoV, NoL );

}

void RE_IndirectDiffuse_Diffraction( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {

	float etaTot = 2.0 * ( uEta1 + uEta2 );
	float diffT = mix( max( 0.0, 1.0 - uF0 - etaTot ), 0.0, uMetal );
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor ) * mix( 0.95, diffT, gCoat );

}

void RE_IndirectSpecular_Diffraction( const in vec3 radiance, const in vec3 irradiance, const in vec3 clearcoatRadiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {

	vec3 V = geometryViewDir;
	vec2 fab = material.dfg;
	float etaTot = 2.0 * ( uEta1 + uEta2 );
	vec3 F0c = mix( vec3( uF0 ), vec3( 0.91 ), uMetal );
	vec3 zero = ( F0c * fab.x + vec3( fab.y ) ) * ( 1.0 - etaTot );
	vec3 fabSpec = vec3( 0.04 ) * fab.x + vec3( fab.y );
	reflectedLight.indirectSpecular += radiance * mix( fabSpec, zero, gCoat );

	#ifdef USE_ENVMAP
	if ( gCoat > 0.001 ) {

		float vt = dot( V, gGrat ), vb = dot( V, gGroove );
		float rough = clamp( material.roughness * 0.75 + uSigma * 2.5, 0.05, 1.0 );
		vec3 acc = vec3( 0.0 );
		for ( int k = 0; k < ${NB}; k ++ ) {

			float q = uBinLambda[ k ] / gPeriod;
			vec3 e = uEta1 * ( lab_order( - vt + q, - vb, rough ) + lab_order( - vt - q, - vb, rough ) );
			if ( uEta2 > 0.0 ) e += uEta2 * ( lab_order( - vt + 2.0 * q, - vb, rough ) + lab_order( - vt - 2.0 * q, - vb, rough ) );
			acc += uBinRGB[ k ] * e;

		}
		reflectedLight.indirectSpecular += acc * gCoat;

	}
	#endif

	float diffT = mix( max( 0.0, 1.0 - uF0 - etaTot ), 0.0, uMetal );
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor ) * mix( vec3( 1.0 ) - fabSpec, vec3( diffT ), gCoat );

	float sheenW = ( 1.0 - gCoat ) * uSheen;
	if ( sheenW > 0.0 ) reflectedLight.indirectSpecular += irradiance * sheenW * uSheenColor * 0.2 * RECIPROCAL_PI;

}

#undef RE_Direct
#undef RE_IndirectDiffuse
#undef RE_IndirectSpecular
#define RE_Direct RE_Direct_Diffraction
#define RE_IndirectDiffuse RE_IndirectDiffuse_Diffraction
#define RE_IndirectSpecular RE_IndirectSpecular_Diffraction
`;

const AFTER_MAP = /* glsl */`
${BAND_SAMPLE_GLSL}
	// stretching the knit spreads the embossed grooves: the period grows with strain
	gPeriod = uPeriod / uThin * ( 1.0 + 0.05 * ( gCell - 0.5 ) * uRandomOrient * step( 0.5, gBrick ) );
`;

const AFTER_NORMAL = /* glsl */`
	{
		vec3 Tv = normalize( tbn[ 0 ] );
		vec3 Bv = normalize( tbn[ 1 ] );
		float ang = uOrient + uRandomOrient * ( gCell - 0.5 ) * 6.2831853 * step( 0.5, gBrick );
		vec3 g = cos( ang ) * Tv + sin( ang ) * Bv;
		gN = normal;
		gGrat = normalize( g - dot( g, normal ) * normal );
		gGroove = normalize( cross( normal, gGrat ) );
	}
`;

const ORIENTATIONS = {
	along: { label: 'Grooves across the band (rainbow sweeps around it)', angle: 0 },
	across: { label: 'Grooves along the band (rainbow sweeps up/down)', angle: 90 },
	diagonal: { label: 'Diagonal grooves (45°)', angle: 45 },
};

export function createDiffractionApproach( { textures, viewer } ) {

	const params = {
		period: 1250,
		orientation: 'along',
		pixelated: 0,
		eta1: 0.10,
		eta2: 0.0,
		f0: 0.16,
		foil: 'transparent',
		sigma: 0.035,
		latticeGain: 1,
		brickGain: 1,
		roughness: 1,
		normalStrength: 1,
	};

	const bins = wavelengthBins( NB, 400, 700 );
	const uniforms = {
		uIridMap: { value: textures.irid },
		uLatticeGain: { value: 1 },
		uBrickGain: { value: 1 },
		uSheen: { value: 0.6 },
		uSheenColor: { value: new THREE.Color( 0xa6bcae ) },
		uTilesPerRing: { value: viewer.ringGeometry.userData.nTiles },
		uPeriod: { value: params.period },
		uEta1: { value: params.eta1 },
		uEta2: { value: params.eta2 },
		uF0: { value: params.f0 },
		uMetal: { value: 0 },
		uSigma: { value: params.sigma },
		uLightSize: { value: 0.02 },
		uOrient: { value: 0 },
		uRandomOrient: { value: 0 },
		uThin: { value: 1 },
		uBinRGB: { value: bins.map( ( b ) => new THREE.Vector3( ...b.rgb ) ) },
		uBinLambda: { value: bins.map( ( b ) => b.lambda ) },
	};

	const material = new THREE.MeshPhysicalMaterial( {
		map: textures.albedo,
		normalMap: textures.normal,
		roughnessMap: textures.orm,
		roughness: 1,
		aoMap: textures.orm,
		metalness: 0,
		ior: 1.5,
	} );
	injectBRDF( material, { uniforms, pars: PARS, afterMap: AFTER_MAP, afterNormal: AFTER_NORMAL, cacheKey: 'lab-diffraction-v1' } );

	return {
		id: 'diffraction',
		material,
		controls: [
			{ key: 'period', label: 'Grating period Λ', type: 'range', min: 500, max: 3000, step: 10, unit: 'nm' },
			{ key: 'orientation', label: 'Groove orientation', type: 'select', options: Object.entries( ORIENTATIONS ).map( ( [ k, v ] ) => ( { value: k, label: v.label } ) ) },
			{ key: 'pixelated', label: 'Per-brick random orientation', type: 'range', min: 0, max: 1, step: 0.01 },
			{ key: 'foil', label: 'Foil build', type: 'select', options: [ { value: 'transparent', label: 'Transparent HRI hologram over yarn' }, { value: 'metal', label: 'Metallised hologram (opaque)' } ] },
			{ key: 'eta1', label: '1st-order efficiency (each side)', type: 'range', min: 0, max: 0.3, step: 0.005 },
			{ key: 'eta2', label: '2nd-order efficiency', type: 'range', min: 0, max: 0.15, step: 0.005 },
			{ key: 'f0', label: 'Zero-order reflectance', type: 'range', min: 0.02, max: 0.5, step: 0.01 },
			{ key: 'sigma', label: 'Angular spread (groove disorder)', type: 'range', min: 0.005, max: 0.2, step: 0.001 },
			{ key: 'latticeGain', label: 'Lattice ground brightness', type: 'range', min: 0.2, max: 1.4, step: 0.01 },
			{ key: 'roughness', label: 'Roughness scale', type: 'range', min: 0.2, max: 1.6, step: 0.01 },
			{ key: 'normalStrength', label: 'Relief (normal map)', type: 'range', min: 0, max: 2, step: 0.01 },
		],
		params,
		set( key, value ) {

			params[ key ] = value;
			switch ( key ) {

				case 'period': uniforms.uPeriod.value = value; break;
				case 'orientation': uniforms.uOrient.value = ORIENTATIONS[ value ].angle * Math.PI / 180; break;
				case 'pixelated': uniforms.uRandomOrient.value = value; break;
				case 'foil':
					uniforms.uMetal.value = value === 'metal' ? 1 : 0;
					if ( value === 'metal' ) {

						params.eta1 = 0.16; uniforms.uEta1.value = 0.16;

					} else {

						params.eta1 = 0.10; uniforms.uEta1.value = 0.10;

					}
					return 'refresh';
				case 'eta1': uniforms.uEta1.value = value; break;
				case 'eta2': uniforms.uEta2.value = value; break;
				case 'f0': uniforms.uF0.value = value; break;
				case 'sigma': uniforms.uSigma.value = value; break;
				case 'latticeGain': uniforms.uLatticeGain.value = value; break;
				case 'roughness': material.roughness = value; break;
				case 'normalStrength': material.normalScale.set( value, value ); break;

			}

		},
		activate( v ) {

			v.setBandMaterial( material );

		},
		beforeRender( v ) {

			uniforms.uThin.value = 1 / ( 1 + v.strain );
			uniforms.uLightSize.value = Math.min( 0.25, v.state.keySize * 0.6 );

		},
		describe() {

			return {
				model: 'Diffraction grating (holographic foil): grating-equation spectral dispersion, Stam lobe for lights',
				period_nm: params.period, orientation: params.orientation, per_brick_random_orientation: params.pixelated,
				foil: params.foil, eta1: params.eta1, eta2: params.eta2, zero_order_f0: params.f0, angular_spread: params.sigma,
			};

		},
	};

}
