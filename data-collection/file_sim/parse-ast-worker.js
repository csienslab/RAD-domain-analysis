const esprima = require('esprima');
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
        const fileContent = fs.readFileSync('./script-files/' + scriptFile, {encoding: 'utf-8'}).trim();

        if(fileContent.length === 0) {
            throw new Error('No content');
        }

        let parsed = JSON.parse(JSON.stringify(esprima.parseScript(fileContent)));

        truncate(parsed);

        fs.writeFileSync(
            './script-files-parsed/' + scriptFile.split('.')[0] + '_parsed.json',
            JSON.stringify(parsed)
        );

    } catch(e) {
        parentPort.postMessage({
            type: 'error',
            file: scriptFile
        });
        // console.error(e);
        return;
    }

    parentPort.postMessage({
        type: 'success',
        file: scriptFile
    });
});
