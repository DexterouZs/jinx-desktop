import * as THREE from 'three';

// Local, reversible remodel of the licensed RPM rig. Existing skinning and all
// facial blend shapes are retained; accessories follow the original head bone.
export function remodelJinx(head) {
 const find=n=>head.scene.getObjectByName(n);
 const face=find('Wolf3D_Head'), skeleton=face.skeleton;
 const materials=[0x087fa5,0x169dba,0x136786].map(color=>new THREE.MeshStandardMaterial({color,roughness:.68,metalness:.03}));
 for(const n of ['Wolf3D_Glasses','Wolf3D_Hair']) find(n).visible=false;
 const root=new THREE.Group(); root.name='Jinx_CustomHair';
 const hi=skeleton.bones.findIndex(b=>b.name==='Head');
 // Model-space geometry -> head bind-space, so nods and turns carry the hair.
 root.applyMatrix4(skeleton.boneInverses[hi]);skeleton.bones[hi].add(root);
 function lock(points,width,depth,material=materials[0],segments=40){
  const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));
  const frames=curve.computeFrenetFrames(segments,false),pos=[],normal=[],indices=[];
  for(let i=0;i<=segments;i++){
   const t=i/segments,p=curve.getPointAt(t),taper=.08+.92*Math.sin(Math.PI*(.12+.87*t))**.35;
   for(let j=0;j<8;j++){
    const a=j/8*Math.PI*2,v=frames.normals[i].clone().multiplyScalar(Math.cos(a)*width*taper).addScaledVector(frames.binormals[i],Math.sin(a)*depth*taper);
    pos.push(p.x+v.x,p.y+v.y,p.z+v.z);normal.push(...v.normalize().toArray());
    if(i<segments){let k=i*8+j,l=i*8+(j+1)%8;indices.push(k,l,k+8,l,l+8,k+8)}
   }
  }
  let g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('normal',new THREE.Float32BufferAttribute(normal,3));g.setIndex(indices);g.computeVertexNormals();
  let m=new THREE.Mesh(g,material);root.add(m);return m;
 }
 // A close-fitting crown under distinct swept locks, instead of the old fringe.
 const cap=new THREE.Mesh(new THREE.SphereGeometry(1,40,24,0,Math.PI*2,0,Math.PI*.58),materials[2]);
 cap.position.set(0,1.674,.028);cap.scale.set(.094,.086,.093);root.add(cap);
 for(let side of [-1,1]){
  for(let j=0;j<23;j++){
   let t=j/22;
   // Long asymmetrical front pieces frame the cheek; rear locks feed the braid.
   const front=.135-t*.23;
   lock([[side*.012,1.756,.04-t*.045],[side*.065,1.749,front*.8],
         [side*(.098+t*.007),1.675,front],
         [side*(.106+t*.007),1.56,front*.72],
         [side*.102,1.465,.065]],.010,.006,materials[j%3]);
  }
  // Three intertwined strands, with tapered ends and small metal ties.
  for(let strand=0;strand<3;strand++){
   let points=[];
   for(let i=0;i<=90;i++){
    let t=i/90,a=t*Math.PI*2*9+strand*Math.PI*2/3,r=.010*(1-t*.45);
    points.push([side*(.111+.045*t)+Math.sin(a)*r,1.50-.58*t,.085+.025*Math.sin(t*3)+Math.cos(a)*r]);
   }
   lock(points,.010,.010,materials[strand],120);
  }
  const tie=new THREE.Mesh(new THREE.TorusGeometry(.014,.003,8,20),new THREE.MeshStandardMaterial({color:0x9d859c,metalness:.7,roughness:.4}));
  tie.rotation.x=Math.PI/2;tie.position.set(side*.153,.98,.093);root.add(tie);
 }
 // The reference's side-swept fringe: broad flowing strips, no straight bangs.
 for(let j=0;j<6;j++){
  let t=j/5;
  lock([[.035-t*.013,1.756,.056],[-.025-t*.006,1.753,.108],[-.062-t*.009,1.704,.13],[-.078-t*.008,1.618,.121],[-.094-t*.007,1.524,.107]],.011,.0045,materials[j%3]);
 }
 // Fine swept crown locks cover the parting and soften the silhouette.
 for(let j=0;j<12;j++){
  let t=j/11;
  lock([[.005+t*.007,1.757,.055-t*.007],[.045+t*.010,1.748,.080+t*.013],[.081+t*.010,1.706,.093+t*.017],[.096+t*.007,1.64,.080+t*.019]],.006,.003,materials[j%3]);
 }
 // Slightly narrower jaw, retaining relative morph deltas and eye alignment.
 const p=face.geometry.attributes.position;
 const factor=y=>1-.07*Math.exp(-(((y-1.552)/.042)**2));
 for(let i=0;i<p.count;i++)p.setX(i,p.getX(i)*factor(p.getY(i)));
 for(const morph of face.geometry.morphAttributes.position||[]){
  for(let i=0;i<morph.count;i++)morph.setX(i,morph.getX(i)*factor(p.getY(i)));
  morph.needsUpdate=true;
 }
 p.needsUpdate=true;face.geometry.computeVertexNormals();
 face.material.roughness=.82;
 face.material.onBeforeCompile=shader=>{
  shader.vertexShader='varying vec3 faceRest;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nfaceRest=position;');
  shader.fragmentShader='varying vec3 faceRest;\n'+shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
   float dark=1.0-smoothstep(.07,.26,dot(diffuseColor.rgb,vec3(.333)));
   float brow=step(1.654,faceRest.y)*step(faceRest.y,1.683);
   float hairline=smoothstep(1.697,1.71,faceRest.y);
   diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.009,.058,.072),dark*max(brow,hairline)*.8);
  `);
 };
 face.material.needsUpdate=true;
 // Recolour iris pixels only, retaining pupils, eye whites and the facial rig.
 const eye=find('EyeLeft').material;
 eye.onBeforeCompile=shader=>{shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
 float iris = (1.0-smoothstep(0.24,0.62,max(diffuseColor.r,max(diffuseColor.g,diffuseColor.b)))) * smoothstep(0.008,0.09,dot(diffuseColor.rgb,vec3(0.333)));
 diffuseColor.rgb=mix(diffuseColor.rgb,vec3(0.30,0.025,0.23),iris*0.48);`)};
 eye.needsUpdate=true;
 // Replace the uniform colours with a charcoal halter, bare shoulders and
 // silver crossed lacing. Rest-space masks stay attached during arm gestures.
 const top=find('Wolf3D_Outfit_Top');
 // Fit the old sleeves closer to the upper arm before colouring them as skin.
 const vertices=top.geometry.attributes.position;
 for(let i=0;i<vertices.count;i++){
  let x=vertices.getX(i),y=vertices.getY(i),z=vertices.getZ(i);
  let blend=THREE.MathUtils.smoothstep(Math.abs(x),.15,.23)*.28;
  let centreZ=.025;
  vertices.setZ(i,z+(centreZ-z)*blend);
 }
 vertices.needsUpdate=true;top.geometry.computeVertexNormals();
 top.material=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.79});
 top.material.onBeforeCompile=shader=>{
  shader.vertexShader='varying vec3 jinxRest;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\njinxRest=position;');
  shader.fragmentShader='varying vec3 jinxRest;\n'+shader.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
 vec3 p=jinxRest;
 vec3 cloth=vec3(.010,.014,.023),skin=vec3(.40,.24,.17);
 float neckline=1.463-0.036*exp(-pow(p.x/.063,2.0));
 float bare=max(smoothstep(neckline-.003,neckline+.003,p.y),smoothstep(.133,.145,abs(p.x)));
 // One pink arm warmer echoes the asymmetric glove in the supplied portrait.
 float sleeve=step(.18,p.x)*(1.0-smoothstep(1.34,1.38,p.y));
 vec3 arm=mix(skin,vec3(.24,.025,.105),sleeve);
 diffuseColor.rgb=mix(cloth,arm,bare);
 float band=step(1.235,p.y)*(1.0-step(1.328,p.y))*step(p.z,.2)*step(.10,p.z);
 float diagonal=min(abs(p.x-(p.y-1.28)*1.1),abs(p.x+(p.y-1.28)*1.1));
 float lace=(1.0-smoothstep(.007,.011,diagonal))*band;
 diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.30,.34,.39),lace);
 float rings=abs(length(vec2(abs(p.x)-.045,abs(p.y-1.28)-.041))-.014);
 float eyelet=(1.0-smoothstep(.002,.004,rings))*step(.10,p.z);
 diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.25,.28,.32),eyelet);

 `);
 };
 top.material.needsUpdate=true;
 return {root,update(time){root.rotation.z=Math.sin(time*.0008)*.006;}};
}
