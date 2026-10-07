// Worker entry: generates the band maps off the main thread.
import { generateBandMaps } from './band.js';

self.onmessage = ( e ) => {

	const m = generateBandMaps( e.data );
	const out = { width: m.width, height: m.height, tileW: m.tileW, brickPitch: m.brickPitch, albedo: m.albedo, normal: m.normal, orm: m.orm, irid: m.irid };
	self.postMessage( out, [ m.albedo.buffer, m.normal.buffer, m.orm.buffer, m.irid.buffer ] );

};
