export const movSimpleVertexShader = `
uniform mat4 matWVP2;
uniform mat4 matW2;
uniform sampler2D fgdepth;
uniform vec3 SphCenter2;
uniform vec3 eyepos;

varying vec2 vUv;
varying vec4 vColor;
varying vec3 vViewDir;
varying vec3 vWorldPos;
varying vec3 vCurrViewDir;

void main() {
    vec3 position = position.xyz;
    vec2 texCoord = uv;
    
    // Get depth value from the texture
    float imgdepth = texture2D(fgdepth, texCoord).r;
    
    // Google jump encoding
    imgdepth = 0.3 / (imgdepth + 0.003);
    
    // Adjust the position by the depth
    vec4 pos = vec4(position.x * imgdepth, position.y * imgdepth, position.z * imgdepth, 1.0);
    
    gl_Position = matWVP2 * pos;
    
    // Calculate world position, view direction, and current view direction
    vWorldPos = (matW2 * pos).xyz;
    vViewDir = normalize(SphCenter2 - vWorldPos);
    vCurrViewDir = normalize(eyepos - vWorldPos);
    
    // Pass the texture coordinates and depth information
    vUv = texCoord;
    vColor.rgb = vec3(imgdepth);
    vColor.a = 1.0;
}
`;

export default movSimpleVertexShader;