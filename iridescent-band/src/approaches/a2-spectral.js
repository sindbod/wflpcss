// Approach 2 — custom spectral layered interference shader (real time).
//
// Physics: an interference layer (film n2, thickness d) on a substrate (n3 + i k3) over a scattering ground.
//   specular  = GGX lobe × Airy reflectance R(θ, d)      (81 wavelengths, s+p polarisation, CIE → sRGB)
//   diffuse   = ground albedo × T(θ_in) × T(θ_out)       (T = 1 − R: the complementary "flop" colour)
// R and T are tabulated per (cos θ, thickness) on the CPU and sampled in the shader.
import * as THREE from 'three';
import { buildFilmLUT, FILM_PRESETS } from '../core/spectral.js';
import { injectBRDF, halfFloatTexture, BAND_GLSL, BAND_SAMPLE_GLSL } from './inject.js';

const LUT_W = 64, LUT_H = 256, D_MAX = 600;

const PARS = /* glsl */`
${BAND_GLSL}
uniform sampler2D uLutR;
uniform sampler2D uLutT;
uniform float uDMax;
uniform float uFilmD;
uniform float uFilmSpread;
uniform float uBrickOffset;
uniform float uLowAmp;
uniform float uThin;
uniform float uFlop;
uniform float uSpecGain;
uniform float uBrickSpec;
uniform float uLightSize;

float gThick;
float gSpec;

vec2 lab_lutUV( float c, float d ) {

	return vec2( clamp( c, 0.0, 1.0 ) * ( ${( LUT_W - 1 ).toFixed( 1 )} / ${LUT_W.toFixed( 1 )} ) + 0.5 / ${LUT_W.toFixed( 1 )},
		clamp( d / uDMax, 0.0, 1.0 ) * ( ${( LUT_H - 1 ).toFixed( 1 )} / ${LUT_H.toFixed( 1 )} ) + 0.5 / ${LUT_H.toFixed( 1 )} );

}
vec3 lab_filmR( float c, float d ) { return texture2D( uLutR, lab_lutUV( c, d ) ).rgb; }
vec3 lab_filmT( float c, float d ) { return texture2D( uLutT, lab_lutUV( c, d ) ).rgb; }

void RE_Direct_Layered( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {

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

	vec3 Ff = lab_filmR( VoH, gThick ) * gSpec;
	vec3 Fd = F_Schlick( vec3( 0.04 ), 1.0, VoH );
	reflectedLight.directSpecular += irradiance * mix( Fd, Ff, gCoat ) * ( D * Vis );

	vec3 Tflop = lab_filmT( NoL, gThick ) * lab_filmT( NoV, gThick );
	vec3 Tflat = vec3( 1.0 - max3( lab_filmR( NoL, gThick ) ) );
	vec3 trans = mix( vec3( 1.0 ) - Fd, mix( Tflat, Tflop, uFlop ), gCoat );
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor ) * trans;

	float sheenW = ( 1.0 - gCoat ) * uSheen;
	if ( sheenW > 0.0 ) reflectedLight.directSpecular += irradiance * sheenW * uSheenColor * lab_charlieD( 0.55, NoH ) * lab_neubeltV( NoV, NoL );

}

void RE_IndirectDiffuse_Layered( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {

	float NoV = saturate( dot( geometryNormal, geometryViewDir ) );
	// incoming light averaged over the hemisphere enters at ~52° on average
	vec3 Tflop = lab_filmT( 0.62, gThick ) * lab_filmT( NoV, gThick );
	vec3 Tflat = vec3( 1.0 - max3( lab_filmR( NoV, gThick ) ) );
	vec3 trans = mix( vec3( 0.95 ), mix( Tflat, Tflop, uFlop ), gCoat );
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor ) * trans;

}

void RE_IndirectSpecular_Layered( const in vec3 radiance, const in vec3 irradiance, const in vec3 clearcoatRadiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {

	// note: for STANDARD materials three.js passes the IBL irradiance here (not to RE_IndirectDiffuse)
	float NoV = saturate( dot( geometryNormal, geometryViewDir ) );
	vec2 fab = material.dfg;
	vec3 specFilm = lab_filmR( NoV, gThick ) * gSpec * ( fab.x + fab.y );
	vec3 specFabric = vec3( 0.04 ) * fab.x + vec3( fab.y );
	reflectedLight.indirectSpecular += radiance * mix( specFabric, specFilm, gCoat );

	vec3 Tflop = lab_filmT( 0.62, gThick ) * lab_filmT( NoV, gThick );
	vec3 Tflat = vec3( 1.0 - max3( lab_filmR( NoV, gThick ) ) );
	vec3 trans = mix( vec3( 1.0 ) - specFabric, mix( Tflat, Tflop, uFlop ), gCoat );
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor ) * trans;

	float sheenW = ( 1.0 - gCoat ) * uSheen;
	if ( sheenW > 0.0 ) reflectedLight.indirectSpecular += irradiance * sheenW * uSheenColor * 0.2 * RECIPROCAL_PI;

}

#undef RE_Direct
#undef RE_IndirectDiffuse
#undef RE_IndirectSpecular
#define RE_Direct RE_Direct_Layered
#define RE_IndirectDiffuse RE_IndirectDiffuse_Layered
#define RE_IndirectSpecular RE_IndirectSpecular_Layered
`;

const AFTER_MAP = /* glsl */`
${BAND_SAMPLE_GLSL}
	gThick = uFilmD * ( 1.0 + uFilmSpread * gThickDev + uBrickOffset * gBrick + uLowAmp * gLow ) * uThin;
	gSpec = uSpecGain * mix( 1.0, uBrickSpec, gBrick );
`;

export function createSpectralApproach( { textures, viewer } ) {

	const params = {
		preset: 'tio2OnMica',
		filmN: FILM_PRESETS.tio2OnMica.n2,
		substrateN: FILM_PRESETS.tio2OnMica.n3,
		substrateK: 0,
		thickness: FILM_PRESETS.tio2OnMica.d,
		spread: 12,
		brickOffset: 3,
		lowFreq: 3,
		flop: 1,
		specGain: 1.6,
		brickSpec: 1.4,
		latticeGain: 1,
		brickGain: 1,
		roughness: 1,
		normalStrength: 1,
		sheen: 0.6,
	};

	let lutR = null, lutT = null;
	const uniforms = {
		uIridMap: { value: textures.irid },
		uLatticeGain: { value: params.latticeGain },
		uBrickGain: { value: params.brickGain },
		uSheen: { value: params.sheen },
		uSheenColor: { value: new THREE.Color( 0xa6bcae ) },
		uTilesPerRing: { value: viewer.ringGeometry.userData.nTiles },
		uLutR: { value: null },
		uLutT: { value: null },
		uDMax: { value: D_MAX },
		uFilmD: { value: params.thickness },
		uFilmSpread: { value: params.spread / 100 },
		uBrickOffset: { value: params.brickOffset / 100 },
		uLowAmp: { value: params.lowFreq / 100 },
		uThin: { value: 1 },
		uFlop: { value: params.flop },
		uSpecGain: { value: params.specGain },
		uBrickSpec: { value: params.brickSpec },
		uLightSize: { value: 0.02 },
	};

	function rebuildLUT() {

		const film = { n2: params.filmN, n3: params.substrateN, k3: params.substrateK };
		const { R, T } = buildFilmLUT( film, { width: LUT_W, height: LUT_H, dMax: D_MAX } );
		if ( lutR ) lutR.dispose();
		if ( lutT ) lutT.dispose();
		lutR = halfFloatTexture( R, LUT_W, LUT_H );
		lutT = halfFloatTexture( T, LUT_W, LUT_H );
		uniforms.uLutR.value = lutR;
		uniforms.uLutT.value = lutT;

	}
	rebuildLUT();
	let lutTimer = null;
	const scheduleLUT = () => {

		clearTimeout( lutTimer );
		lutTimer = setTimeout( rebuildLUT, 60 );

	};

	const material = new THREE.MeshPhysicalMaterial( {
		map: textures.albedo,
		normalMap: textures.normal,
		roughnessMap: textures.orm,
		roughness: params.roughness,
		aoMap: textures.orm,
		metalness: 0,
		ior: 1.5,
	} );
	injectBRDF( material, { uniforms, pars: PARS, afterMap: AFTER_MAP, cacheKey: 'lab-layered-v1' } );

	return {
		id: 'spectral',
		material,
		controls: [
			{ key: 'preset', label: 'Layer stack', type: 'select', options: Object.entries( FILM_PRESETS ).map( ( [ k, v ] ) => ( { value: k, label: v.label } ) ) },
			{ key: 'thickness', label: 'Film thickness', type: 'range', min: 40, max: 560, step: 1, unit: 'nm' },
			{ key: 'filmN', label: 'Film index n₂', type: 'range', min: 1.2, max: 2.8, step: 0.01 },
			{ key: 'substrateN', label: 'Substrate index n₃', type: 'range', min: 1.0, max: 2.6, step: 0.01 },
			{ key: 'substrateK', label: 'Substrate absorption k₃', type: 'range', min: 0, max: 8, step: 0.1 },
			{ key: 'spread', label: 'Per-cell thickness jitter', type: 'range', min: 0, max: 30, step: 1, unit: '%' },
			{ key: 'brickOffset', label: 'Brick vs lattice thickness', type: 'range', min: - 15, max: 15, step: 1, unit: '%' },
			{ key: 'lowFreq', label: 'Slow thickness drift', type: 'range', min: 0, max: 15, step: 0.5, unit: '%' },
			{ key: 'flop', label: 'Complementary flop', type: 'range', min: 0, max: 1, step: 0.01 },
			{ key: 'specGain', label: 'Stacked-platelet reflectance gain', type: 'range', min: 0, max: 3, step: 0.01 },
			{ key: 'brickSpec', label: 'Brick floats gloss (× reflectance)', type: 'range', min: 0.5, max: 2.5, step: 0.01 },
			{ key: 'latticeGain', label: 'Lattice ground brightness', type: 'range', min: 0.2, max: 1.4, step: 0.01 },
			{ key: 'brickGain', label: 'Brick ground brightness', type: 'range', min: 0.2, max: 3, step: 0.01 },
			{ key: 'roughness', label: 'Roughness scale', type: 'range', min: 0.2, max: 1.6, step: 0.01 },
			{ key: 'normalStrength', label: 'Relief (normal map)', type: 'range', min: 0, max: 2, step: 0.01 },
		],
		params,
		set( key, value ) {

			params[ key ] = value;
			switch ( key ) {

				case 'preset': {

					const p = FILM_PRESETS[ value ];
					params.filmN = p.n2; params.substrateN = p.n3; params.substrateK = p.k3 || 0; params.thickness = p.d;
					uniforms.uFilmD.value = p.d;
					rebuildLUT();
					return 'refresh';

				}
				case 'filmN': case 'substrateN': case 'substrateK': scheduleLUT(); break;
				case 'thickness': uniforms.uFilmD.value = value; break;
				case 'spread': uniforms.uFilmSpread.value = value / 100; break;
				case 'brickOffset': uniforms.uBrickOffset.value = value / 100; break;
				case 'lowFreq': uniforms.uLowAmp.value = value / 100; break;
				case 'flop': uniforms.uFlop.value = value; break;
				case 'specGain': uniforms.uSpecGain.value = value; break;
				case 'brickSpec': uniforms.uBrickSpec.value = value; break;
				case 'latticeGain': uniforms.uLatticeGain.value = value; break;
				case 'brickGain': uniforms.uBrickGain.value = value; break;
				case 'roughness': material.roughness = value; break;
				case 'normalStrength': material.normalScale.set( value, value ); break;

			}

		},
		activate( v ) {

			v.setBandMaterial( material );

		},
		beforeRender( v ) {

			uniforms.uThin.value = 1 / ( 1 + 0.45 * v.strain );
			uniforms.uLightSize.value = Math.min( 0.25, v.state.keySize * 0.6 );

		},
		describe() {

			return {
				model: 'Layered interference: Airy thin film (81 λ, s+p) over scattering ground, film-transmission diffuse',
				film_index: params.filmN, substrate_index: params.substrateN, substrate_k: params.substrateK,
				film_thickness_nm: params.thickness, per_cell_jitter_pct: params.spread, brick_offset_pct: params.brickOffset,
				slow_drift_pct: params.lowFreq, flop: params.flop, reflectance_gain: params.specGain, brick_gloss: params.brickSpec,
				lattice_gain: params.latticeGain, brick_gain: params.brickGain, roughness_scale: params.roughness,
			};

		},
	};

}
