
const fs = require('fs');
function tryReq(n){ try { return require(n); } catch { return null; } }
const acorn = tryReq('acorn') || require('acorn');
const acornJsx = tryReq('acorn-jsx');
const acornTs  = tryReq('acorn-typescript');

const filename = process.argv[2];
const src = fs.readFileSync(filename, 'utf8');

let Parser = acorn.Parser;
if (acornJsx) Parser = Parser.extend(acornJsx());
if (acornTs)  Parser = Parser.extend(acornTs());

let tree;
try {
  tree = Parser.parse(src, { ecmaVersion: 'latest', sourceType: 'module' });
} catch (e) {
  console.error('PARSE_ERR', e.message);
  console.log('[]');
  process.exit(0);
}

const names = new Set();
function add(n){ if(n) names.add(n); }

function walk(node){
  if (!node || typeof node !== 'object') return;
  switch(node.type){
    case 'FunctionDeclaration':
      add(node.id && node.id.name);
      break;
    case 'VariableDeclaration':
      for (const d of node.declarations || []) {
        if (d.id && d.id.name && (d.init && (d.init.type === 'ArrowFunctionExpression' || d.init.type === 'FunctionExpression'))) {
          add(d.id.name);
        }
      }
      break;
    case 'ClassDeclaration':
      add(node.id && node.id.name);
      break;
  }
  for (const k of Object.keys(node)) {
    const v = node[k];
    if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') walk(v);
  }
}

walk(tree);
console.log(JSON.stringify(Array.from(names)));
