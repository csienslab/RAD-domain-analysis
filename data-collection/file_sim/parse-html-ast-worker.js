const esprima = require('esprima');
const HTMLParser = require('node-html-parser');
const { parentPort } = require('worker_threads');
const fs = require('fs');

function truncate(tree){
    let hasType = false;
    if(Array.isArray(tree)){
        tree = tree.filter(x => truncate(x));
        hasType = tree.length > 0
    } else if(tree !== null && typeof tree === "object"){
        for(const k of Object.keys(tree)){
            if(k === 'type'){
                hasType = true;
                continue
            }
            if(!truncate(tree[k])){
                delete tree[k];
            }
        }
    }

    return hasType
}

parentPort.on('message', (scriptFile) => {
    try {
        const root = HTMLParser.parse(fs.readFileSync('./script-files/' + scriptFile, {encoding: 'utf-8'}));
        let parsed = [];
        for(const ele of root.querySelectorAll('script')){
            if(!('src' in ele.attrs) && ele.rawText.trim() !== '') {
                let p = JSON.parse(JSON.stringify(esprima.parseScript(ele.rawText)));
                truncate(p);
                parsed.push(JSON.stringify(p));
            }
        }

        if(parsed.length !== 0){
            fs.writeFileSync(
                './script-files-parsed/' + scriptFile.split('.')[0] + '_parsed_html.json',
                parsed.join('\n')
            );
        }

    } catch(e) {
        parentPort.postMessage({
            type: 'error',
            file: scriptFile
        });
        return;
    }

    parentPort.postMessage({
        type: 'success',
        file: scriptFile
    });
});
