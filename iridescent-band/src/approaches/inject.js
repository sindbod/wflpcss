// Replace three.js' physical BRDF (RE_Direct / RE_IndirectDiffuse / RE_IndirectSpecular) on a
// MeshPhysicalMaterial while keeping its lights, shadows, PMREM environment, normal maps and tone mapping.
import * as THREE from 'three';

export function injectBRDF( material, { uniforms, pars, afterMap = '', afterNormal = '', cacheKey } ) {

	material.onBeforeCompile = ( shader ) => {

		Object.assign( shader.uniforms, uniforms );
		shader.fragmentShader = shader.fragmentShader
			.replace( '#include <lights_physical_pars_fragment>', `#include <lights_physical_pars_fragment>\n${pars}\n` )
			.replace( '#include <map_fragment>', `#include <map_fragment>\n${afterMap}\n` )
			.replace( '#include <normal_fragment_maps>', `#include <normal_fragment_maps>\n${afterNormal}\n` );

	};
	material.customProgramCacheKey = () => cacheKey;
	material.needsUpdate = true;

}

// RGBA float array -> half-float DataTexture with linear filtering.
export function halfFloatTexture( data, width, height ) {

	const half = new Uint16Array( data.length );
	for ( let i = 0; i < data.length; i ++ ) half[ i ] = THREE.DataUtils.toHalfFloat( data[ i ] );
	const t = new THREE.DataTexture( half, width, height, THREE.RGBAFormat, THREE.HalfFloatType );
	t.magFilter = THREE.LinearFilter;
	t.minFilter = THREE.LinearFilter;
	t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
	t.generateMipmaps = false;
	t.colorSpace = THREE.NoColorSpace;
	t.needsUpdate = true;
	return t;

}

// Shared GLSL: band parameters sampled once per fragment + fabric sheen for the plain sage areas.
export const BAND_GLSL = /* glsl */`
uniform sampler2D uIridMap;
uniform float uLatticeGain;
uniform float uBrickGain;
uniform float uSheen;
uniform vec3 uSheenColor;
uniform float uTilesPerRing;

float gCoat;
float gBrick;
float gCell;
float gThickDev;
float gLow;

float lab_charlieD( float rough, float NoH ) {

	float invAlpha = 1.0 / rough;
	float cos2h = NoH * NoH;
	float sin2h = max( 1.0 - cos2h, 0.0078125 );
	return ( 2.0 + invAlpha ) * pow( sin2h, invAlpha * 0.5 ) / ( 2.0 * PI );

}

float lab_neubeltV( float NoV, float NoL ) {

	return saturate( 1.0 / ( 4.0 * ( NoL + NoV - NoL * NoV ) ) );

}
`;

export const BAND_SAMPLE_GLSL = /* glsl */`
	vec4 iridTexel = texture2D( uIridMap, vMapUv );
	gCoat = iridTexel.r;
	gBrick = iridTexel.b;
	gCell = iridTexel.a;
	gThickDev = ( iridTexel.g - 0.5 ) * 2.0;
	{
		// slow, ring-periodic drift of the coating thickness (non-repeating across tiles)
		float sB = vMapUv.x / uTilesPerRing * 6.2831853;
		gLow = 0.55 * sin( 3.0 * sB + 1.3 ) + 0.3 * sin( 7.0 * sB + 0.4 + 2.0 * vMapUv.y ) + 0.15 * sin( 13.0 * sB + 2.1 );
	}
	diffuseColor.rgb *= mix( 1.0, mix( uLatticeGain, uBrickGain, gBrick ), step( 0.01, gCoat ) );
`;
