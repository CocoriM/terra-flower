/**
 * Aurora Borealis / Australis renderer for CesiumJS.
 *
 * Creates animated translucent curtain ribbons at polar latitudes (65°–75° N/S)
 * using Cesium Entity walls with a custom material for animation.
 *
 * Intensity is driven by month: strongest near winter solstice.
 */

const NUM_POINTS = 120; // points around the aurora ring
const CURTAIN_MIN_ALT = 100_000; // base altitude in meters
const CURTAIN_MAX_ALT = 300_000; // top altitude in meters

/**
 * Compute aurora intensity based on month.
 * Northern aurora peaks Dec/Jan, southern peaks Jun/Jul.
 */
function auroraIntensity(month: number, isNorth: boolean): number {
    const peakMonth = isNorth ? 12 : 6;
    const diff = Math.abs(month - peakMonth);
    const dist = Math.min(diff, 12 - diff);
    return Math.max(0.15, 1.0 - dist * 0.14);
}

/**
 * Generate positions for an aurora ring at a given center latitude.
 */
function generateRingPositions(
    Cesium: any,
    centerLat: number,
    latSpread: number,
): any[] {
    const positions: any[] = [];
    for (let i = 0; i <= NUM_POINTS; i++) {
        const frac = i / NUM_POINTS;
        const lon = -180 + frac * 360;
        // Wobble latitude for natural curtain shape
        const wobble = Math.sin(frac * Math.PI * 12) * latSpread +
            Math.sin(frac * Math.PI * 5 + 1.7) * latSpread * 0.5;
        const lat = centerLat + wobble;
        positions.push(Cesium.Cartographic.fromDegrees(lon, lat));
    }
    return positions;
}

export interface AuroraHandle {
    intensityN: number;
    intensityS: number;
    cleanup: () => void;
}

/**
 * Create aurora visualization and add to the viewer.
 * Returns a handle to update intensity and clean up.
 */
export function createAurora(viewer: any, initialMonth: number): AuroraHandle {
    const Cesium = window.Cesium;
    const scene = viewer.scene;

    const handle: AuroraHandle = {
        intensityN: auroraIntensity(initialMonth, true),
        intensityS: auroraIntensity(initialMonth, false),
        cleanup: () => {},
    };

    // We use a simpler but reliable approach: multiple translucent
    // wall entities with color callbacks that animate over time.
    const startTime = Date.now();
    const entities: any[] = [];

    function createCurtainStrip(
        centerLat: number,
        isNorth: boolean,
        hueShift: number,
    ): void {
        // Build positions array (degrees)
        const degreesArray: number[] = [];
        for (let i = 0; i <= NUM_POINTS; i++) {
            const frac = i / NUM_POINTS;
            const lon = -180 + frac * 360;
            const wobble =
                Math.sin(frac * Math.PI * 12 + hueShift) * 2.5 +
                Math.sin(frac * Math.PI * 5 + 1.7 + hueShift) * 1.5;
            const lat = centerLat + wobble;
            degreesArray.push(lon, lat);
        }

        const positions = Cesium.Cartesian3.fromDegreesArray(degreesArray);

        // Color callback for animation
        const colorCallback = new Cesium.CallbackProperty(() => {
            const elapsed = (Date.now() - startTime) / 1000;
            const intensity = isNorth ? handle.intensityN : handle.intensityS;

            // Pulsing green with slight blue tint
            const pulse = 0.7 + 0.3 * Math.sin(elapsed * 0.5 + hueShift);
            const green = 0.6 + 0.3 * pulse;
            const blue = 0.2 + 0.15 * Math.sin(elapsed * 0.3 + hueShift * 2);
            const red = 0.05 + 0.1 * Math.sin(elapsed * 0.7 + hueShift * 3);
            const alpha = intensity * pulse * 0.35;

            return new Cesium.Color(red, green, blue, alpha);
        }, false);

        const entity = viewer.entities.add({
            wall: {
                positions: positions,
                minimumHeights: new Array(positions.length).fill(CURTAIN_MIN_ALT),
                maximumHeights: new Array(positions.length).fill(CURTAIN_MAX_ALT),
                material: new Cesium.ColorMaterialProperty(colorCallback),
            },
        });

        entities.push(entity);
    }

    // Create multiple overlapping curtain strips for depth
    // Northern aurora: 3 strips at slightly different latitudes
    createCurtainStrip(68, true, 0);
    createCurtainStrip(70, true, 2.0);
    createCurtainStrip(72, true, 4.5);

    // Southern aurora: 3 strips
    createCurtainStrip(-68, false, 1.0);
    createCurtainStrip(-70, false, 3.0);
    createCurtainStrip(-72, false, 5.5);

    handle.cleanup = () => {
        for (const entity of entities) {
            viewer.entities.remove(entity);
        }
        entities.length = 0;
    };

    return handle;
}

/**
 * Update aurora intensity when the month changes.
 */
export function updateAuroraMonth(handle: AuroraHandle, month: number): void {
    handle.intensityN = auroraIntensity(month, true);
    handle.intensityS = auroraIntensity(month, false);
}
