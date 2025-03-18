const bgSimpleVertexShader = `
uniform mat4 matWVP;

uniform sampler2D depthbg;
uniform sampler2D depthfg;
uniform sampler2D depthfront;

varying vec2 vUv;
varying vec4 vColor;

void main() {
    vec3 position = position.xyz;
    vec2 texCoord = uv;
    
    float dbbg = texture2D(depthbg, texCoord).r;
    float dbg = texture2D(depthfg, texCoord).r;
    float dfront = texture2D(depthfront, texCoord).r;
    float imgdepth = min(dbbg, dbg);
    imgdepth = min(imgdepth, dfront);
    
    // Google jump encoding
    imgdepth = 0.3 / (imgdepth + 0.001);
    
    vec4 pos = vec4(position.x * imgdepth, position.y * imgdepth, position.z * imgdepth, 1.0);
    
    gl_Position = matWVP * pos;
    
    vUv = texCoord;
    vColor.rgb = vec3(imgdepth);
    vColor.a = 1.0;
}
`;

export default bgSimpleVertexShader;