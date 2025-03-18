const movSimpleFragmentShader = `
uniform sampler2D fgtext;
uniform sampler2D alphamask;
uniform vec3 spherecenter;
uniform vec3 eyepos;
uniform vec3 headposition;
uniform float desat;
uniform float colored;

varying vec2 vUv;
varying vec3 vWorldPos;

#define M_E 2.7182818284590452353602874713526

void main() {
    float dist = 0.05 + sqrt(
        pow(headposition.y - spherecenter.y, 2.0) +
        pow(headposition.z - spherecenter.z, 2.0) +
        pow(headposition.z - spherecenter.z, 2.0)
    );

    vec3 fgbcolor = texture2D(fgtext, vUv).rgb;
    float alpha = texture2D(alphamask, vUv).r;

    float k = 30.0;
    float c = 0.15;
    float Scurve = 1.0 / (1.0 + pow(M_E, -k * (dist - c)));

    float corrected = abs((1.0 - Scurve) * 1.0 + alpha * Scurve);
    vec3 gray = vec3(dot(vec3(0.2126, 0.7152, 0.0722), fgbcolor));
    vec3 desaturated = mix(fgbcolor, gray, desat);

    if (colored == 0.0) {				
        gl_FragColor = vec4(desaturated, corrected);
    } else {
        vec3 yellow = vec3(0.9, 0.8, 0.2);
        vec3 yellowish = mix(desaturated, yellow, 0.5);
        gl_FragColor = vec4(yellowish, corrected);
    }
}
`;

export default movSimpleFragmentShader;