const fgSimpleVertexShader = `
uniform mat4 matWVP2;
uniform sampler2D fgdepth;
uniform sampler2D frontdepth;

varying vec2 vUv;
varying vec4 vColor;

void main() {
    vec3 position = position.xyz;
    vec2 texCoord = uv;
    
    // Get depth values from the textures
    float bdepth = texture2D(fgdepth, texCoord).r;
    float fdepth = texture2D(frontdepth, texCoord).r;
    
    // Use the minimum depth
    float imgdepth = min(bdepth, fdepth);
    
    // Google Jump encoding
    imgdepth = 0.3 / (imgdepth + 0.002);
    
    // Adjust the position by the depth
    vec4 pos = vec4(position.x * imgdepth, position.y * imgdepth, position.z * imgdepth, 1.0);
    
    gl_Position = matWVP2 * pos;
    
    vUv = texCoord;
    vColor.rgb = vec3(imgdepth);
    vColor.a = 1.0;
}
`;

export default fgSimpleVertexShader;