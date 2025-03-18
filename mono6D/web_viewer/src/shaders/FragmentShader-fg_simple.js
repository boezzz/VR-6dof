const fgSimpleFragmentShader = `
uniform sampler2D fgtext;
uniform sampler2D alphamask;
uniform float desat;
uniform float colored;

varying vec2 vUv;

void main() {
    vec3 fgbcolor = texture2D(fgtext, vUv).rgb;
    float mask = texture2D(alphamask, vUv).r;		

    vec3 gray = vec3(dot(vec3(0.2126, 0.7152, 0.0722), fgbcolor));
    vec3 desaturated = mix(fgbcolor, gray, desat);
    desaturated = mix(fgbcolor, desaturated, 0.5);

    if (colored == 0.0) {				
        gl_FragColor = vec4(desaturated, mask);
    } else {
        vec3 green = vec3(0.1, 0.9, 0.7);
        vec3 greenish = mix(desaturated, green, 0.5);
        gl_FragColor = vec4(greenish, mask);
    }
}
`;

export default fgSimpleFragmentShader;