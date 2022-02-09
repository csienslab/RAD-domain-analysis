const { Worker } = require('worker_threads');
const fs = require('fs');

function getFiles() {
    const doneFiles = new Set(fs.readdirSync('./script-files-parsed').map(file => file.replace('_parsed_html.json', '')));
    const filesToBeProcessed = new Set(fs.readdirSync('./script-files').filter(file => !doneFiles.has(file)));

    return filesToBeProcessed;
}

function assignFile(filesToBeProcessed, filesProcessing, worker) {
    let f;
    if(filesToBeProcessed.size == 0){
        f = false;
    }
    f = filesToBeProcessed[Symbol.iterator]().next().value;
    filesToBeProcessed.delete(f);

    if(f){
        filesProcessing.add(f);
        worker.postMessage(f);
    } else if(filesToBeProcessed.size + filesProcessing.size === 0) {
        setTimeout(() => {
            process.exit(0);
        },10 * 1000);
    }
}

const filesToBeProcessed = getFiles();
const filesProcessing = new Set();
const workerNum = 36;
const workers = [];

while(workers.length < workerNum) {
    let index = workers.push(new Worker('./parse-html-ast-worker.js')) - 1;
    workers[index].on('message', (msg) => {

        if((filesToBeProcessed.size + filesProcessing.size) % 1000 === 0 ||
            (filesToBeProcessed.size + filesProcessing.size) < 100){
            console.log('left',  (filesToBeProcessed.size + filesProcessing.size));
        }

        filesProcessing.delete(msg?.file);
        assignFile(filesToBeProcessed, filesProcessing, workers[index]);
    });
    assignFile(filesToBeProcessed, filesProcessing, workers[index]);
}