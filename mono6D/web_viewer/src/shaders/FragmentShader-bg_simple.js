const bgSimpleFragmentShader = `
uniform sampler2D bgtext;

uniform float desat;
uniform float colored;

varying vec2 vUv;

void main() {
    vec3 rgbcolor = texture2D(bgtext, vUv).rgb;
    vec3 gray = vec3(dot(vec3(0.2126, 0.7152, 0.0722), rgbcolor));
    vec3 desaturated = mix(rgbcolor, gray, desat);

    if (colored == 0.0) {
        gl_FragColor = vec4(desaturated, 1.0);
    } else {
        vec3 purple = vec3(0.4, 0.1, 0.8);
        vec3 purpleish = mix(desaturated, purple, 0.5);
        gl_FragColor = vec4(purpleish, 1.0);
    }
}
`;

export default bgSimpleFragmentShader;
