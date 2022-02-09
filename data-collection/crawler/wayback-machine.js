#!/usr/bin/env node
'use strict';

const puppeteer = require('puppeteer-extra');
const PuppeteerBlocker = require('@cliqz/adblocker-puppeteer');
const fs = require('fs');
const util = require('util');
const url_parse = require('url').parse;
const mysql = require('mysql2/promise');
const cliProgress = require('cli-progress');
const argv = require('minimist')(process.argv.slice(2));
const config = {
    domain: argv.domain || 'snapshot.json',
    log: argv.log || 'log.txt',
    proxyList: argv.proxy || 'proxyList.txt',
    finishedList: argv.finishedList || 'finishedList.txt',
    browseTimeMs: argv.browseTimeMs || (90 * 1000),
    tabNum: argv.tabNum || 6,
    headless: String(argv.headless || 'true').toLowerCase() === 'true',
    outputLog: String(argv.outputLog || 'false').toLowerCase() === 'true',
    retryTimes:  argv.retryTimes || 10,
    blockAds: String(argv.blockAds || 'true').toLowerCase() === 'true',
    // When running on mulitple different machines
    machineCount: argv.machineCount,
    machineIndex: argv.machineIndex
};

process.setMaxListeners(0);

/* Stealth */
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

/* Logging */
const cmdLogFile = fs.createWriteStream(config.log, {flags : 'a'});
const log = function() {
    if(config.outputLog)
        process.stderr.write(util.format.apply(null, arguments) + '\n');
    cmdLogFile.write(util.format.apply(null, arguments) + '\n');
};
const logError = function() {
    process.stderr.write(util.format.apply(null, arguments) + '\n');
    cmdLogFile.write(util.format.apply(null, arguments) + '\n');
};
const logTime = () => JSON.stringify(new Date()).split('"')[1];

log(new Date().toString());
log(config);

/* MySQL Connection */
const pool = mysql.createPool({
    //connectionLimit : 50,
    host: '<redacted>',
    user: '<redacted>',
    password: '<redacted>',
    database: 'wayback_machine_crawl',
    connectionLimit: config.tabNum * 10
});

/* Blocklists */
const get_blocklists = async (d) => {
    let blocklists = await fs.promises.readdir("../ad/history");
    return Promise.all(blocklists.map(async (b) => {
        let t = Math.max.apply(Math, (await fs.promises.readdir("../ad/history/" + b)).map(d => parseInt(d)).filter(x => x <= d));
	return t > 0 ? "../ad/history/" + b + '/' + t.toString() : null;
    }));
}

!async function() {
    let tabs = [];

    const browseTimeMs = config.browseTimeMs;
    const tabNums = config.tabNum;
    let wmList = JSON.parse(await fs.promises.readFile(config.domain, {encoding: 'utf-8'}));
    let proxyList = (await fs.promises.readFile(config.proxyList, {encoding: 'utf-8'})).trim().split('\n');
    proxyList = proxyList.length > 0 ? proxyList : [null];
    let finishedList = (await fs.promises.readFile(config.finishedList, {encoding: 'utf-8'})).trim().split('\n').filter(Boolean);
    let uncrawledUrlSet = [];
    let progressBar = undefined;

    let connection_for_validation = await pool.getConnection();

    const saveAndExit = () => {
        log("Save And Exit")
        Promise.all([...Array(proxyList.length).keys()].map((index) => killBrowser(index))).then(async () => {
            log('write crawled url');
            await fs.promises.writeFile(config.finishedList, Array.from(finished).join('\n'));
            process.exit(0);
        });
    }
    const killBrowser = async (browserId) => {
        log(new Date().toString());
        log('Gracefully stop the process......');
        log('Closing the browser ' + browserId);
        await browsers[browserId].close();
    };
    process.on('SIGINT', () => {
        log(`Recieved SIGINT, exiting`);
        saveAndExit();
    });

    const finished = new Set(finishedList);

    const browse = (id, browserId, url, originalDomain, sleepMs, retry) => new Promise(async (resolve, reject) => {
        let datetime = url.substr(28, 4) + '-' + url.substr(32, 2) + '-' + url.substr(34, 2) + ' ' + url.substr(36, 2) + ':' + url.substr(38, 2) + ':' + url.substr(40, 2);
        if(!((new Date(datetime) !== "Invalid Date") && !isNaN(new Date(datetime)))){
            logError(`${logTime()} ${logTime()} browser ${browserId} tab ${id}: ${url} can't parse datetime`);
            datetime = null;
        }

        // check DB if there were existing records, if so, this snapshot had been crawled.
        if(true){
            // parse and validate date of snapshot
            const [rows_, fields_] = await connection_for_validation.query('SELECT id FROM requests where domain = ? and datetime = ? LIMIT 1', [originalDomain, datetime]);
            if(rows_.length > 0) {
                if(!finished.has(url)){
                    finished.add(url);
                    progressBar.increment();
                    // await fs.promises.writeFile(config.finishedList, Array.from(finished).join('\n'));
                }

                log(`${logTime()} Has crawled ${url} (in DB), pass.`);
                resolve({ tabId: id, hasError: false });
                return;
            }
        }

        if (typeof sleepMs !== 'undefined') {
            log(`${logTime()} browser ${browserId} tab ${id}: sleep for ${sleepMs} msec....`);
            await new Promise(r => setTimeout(r, sleepMs));
        }

        let requests = [];
        const context = await browsers[browserId].createIncognitoBrowserContext();
        const page = await context.newPage();
        //const page = await browsers[browserId].newPage();

        let dontCallClose = false;

        // Prepare Adblocker
        const blocker = PuppeteerBlocker.PuppeteerBlocker.parse(
            (await get_blocklists((new Date(datetime)) / 1000))
            .filter(a => a)
            .map(b => fs.readFileSync(b, 'utf-8'))
            .join("\n")
        );

        // Intercept requests
        await page.setRequestInterception(true);
        page.on('domcontentloaded', (frame) => blocker.onFrameNavigated(page.mainFrame()));
        page.on('frameattached', (frame) => blocker.onFrameNavigated(frame));
        page.on('request', (req) => {
            const { redirect, match, filter } = blocker.match(PuppeteerBlocker.fromPuppeteerDetails(req));
            if (config.blockAds && redirect !== undefined) {
                req.respond({
                    body: redirect.body,
                    contentType: redirect.contentType,
                });
            } else if (config.blockAds && match === true) {
                requests.push({ url: req.url(), initiator: req.initiator(), blocked: true, filter: filter });
                req.abort();
            } else {
                // ignore data:
                if(req.url().startsWith("data:")){
                    req.continue();
                    return;
                }

                let parsedUrl = url_parse(req.url());
                // request from wayback machine itself
                if(parsedUrl.hostname.endsWith("archive.org")){
                    // the cache is located at https://web.archive.org/web
                    if(parsedUrl.hostname == "web.archive.org" && parsedUrl.pathname.startsWith("/web")){
                        requests.push({ url: req.url(), initiator: req.initiator(), blocked: false });
                    }
                    // otherwise ignore
                    req.continue();
                }else{
                    // all outgoing requests should be recorded and aborted to prevent the live sources from polluting the results
                    requests.push({ url: req.url(), initiator: req.initiator(), blocked: false });
                    req.abort();
                }
            }
        });

        page.on('response', async (response) => {
            // if rate limit exceed
            if(response.status() == 429 && !dontCallClose){
                dontCallClose = true;
                log(`${logTime()} browser ${browserId} tab ${id}: ${url} rate limit exceed, retry ${retry}`);
                uncrawledUrlSet[browserId].add({
                    url: url,
                    original_domain: originalDomain
                });
            	await page.close().catch();
                resolve({ tabId: id, hasError: true });
            }
        })
        page._onTargetCrashed = () => {
            logError('Page crashed! Please try to reduce the number of tabs.');
            saveAndExit();
        };

        const closeAndLog = async (err) => {
            if (dontCallClose)
                return;
            dontCallClose = true;

            if (typeof err !== 'undefined'){
                log(`${logTime()} browser ${browserId} tab ${id}: `, url, 'retry: ', retry, err.message);
                uncrawledUrlSet[browserId].add({
                    url: url,
                    original_domain: originalDomain
                });
            }
            await page.close().catch();
            if(typeof err !== 'undefined'){
                resolve({ tabId: id, hasError: true });
                return;
            }

            // write to db
            let bulkInsert = [];
            requests.forEach((req) => {
                if(req.url.startsWith("https://archive.org/includes/analytics.js") || req.url.startsWith("https://web.archive.org/client_204")){
                    return;
                }

                let initiator = JSON.parse(JSON.stringify(req.initiator));
                if(initiator.type == "script" && typeof initiator.stack.callFrames === "object"){
                    // remove element rewrite by wayback machine
                    initiator.stack.callFrames = initiator.stack.callFrames.filter(m => !m.url.includes("https://web.archive.org/_static/js/wombat.js"))
                }

                bulkInsert.push([
                    originalDomain, // domain
                    datetime, // datetime
                    req.url.replace(/^(http|https):\/\/web\.archive\.org\/web\/\w+\//g, ""), // request
                    JSON.stringify(initiator).replace(/(http|https):\/\/web\.archive\.org\/web\/\w+\//g, ""), // initiator
                    req.blocked,
                    req.blocked ? JSON.stringify(req.filter) : null
                ]);
            });
            if(bulkInsert.length <= 0){
                resolve({ tabId: id, hasError: true });
                return;
            }

            let connection = null;
            try{
                connection = await pool.getConnection();
                await connection.query('START TRANSACTION'); // mysql2 with promise doesn't support beginTransaction
                let rows = await connection.query('INSERT INTO requests (domain, datetime, request, initiator, blocked, filter) VALUES ?', [bulkInsert]);
                await connection.query('COMMIT');

                await connection.release();
                log(`${logTime()} browser ${browserId} tab ${id}: ${url} write ${rows[0].affectedRows} records to DB successfully`)
                if(!finished.has(url)){
                    finished.add(url);
                    progressBar.increment();
                    await fs.promises.writeFile(config.finishedList, Array.from(finished).join('\n'));
                }
            } catch(err) {
                logError(`${logTime()} browser ${browserId} tab ${id}: `, err);
                try{
                    await connection.query('ROLLBACK');
                    await connection.release();
                }catch(e){}
            }
            await context.close();
            resolve({ tabId: id, hasError: false });
        };

        // browsing
        page.goto(url, {timeout: 0}).catch(closeAndLog);
        setTimeout(closeAndLog, browseTimeMs);
    });

    let domainList = Object.keys(wmList);
    // flatten the array
    let crawlUrls = [];
    domainList.forEach((domain) => {
        if(wmList[domain] == null)
            return;
        if(wmList[domain].length <= 1)
            return;

        wmList[domain].forEach((url) => {
            crawlUrls.push({
                url: url,
                original_domain: domain
            });
        });
    });

    // progress bar
    progressBar = new cliProgress.SingleBar({
        barsize: 80,
        stopOnComplete: true,
        format: 'progress [{bar}] {percentage}% | ETA: {eta_formatted} | Duration: {duration_formatted} | {value}/{total}'
    }, cliProgress.Presets.shades_grey);

    // shuffle
    function shuffle(a) {
        var j, x, i;
        for (i = a.length - 1; i > 0; i--) {
            j = Math.floor(Math.random() * (i + 1));
            x = a[i];
            a[i] = a[j];
            a[j] = x;
        }
        return a;
    }

    // assign url to each browser
    let chunkArray = (arr, chunkCount) => {
        const chunks = [];
        while(arr.length) {
            const chunkSize = Math.ceil(arr.length / chunkCount--);
            const chunk = arr.slice(0, chunkSize);
            chunks.push(shuffle(chunk));
            arr = arr.slice(chunkSize);
        }
        return chunks;
    }

    if(typeof config.machineCount !== "undefined" && typeof config.machineIndex !== "undefined" ){
        let temp = chunkArray(crawlUrls, config.machineCount);
        crawlUrls = temp[config.machineIndex];
    }
    progressBar.start(crawlUrls.length, finished.size);
    crawlUrls = chunkArray(shuffle(crawlUrls), proxyList.length);

    // start browser
    let browsers = [];
    for(let i = 0; i < proxyList.length; i++){
        let proxy = proxyList[i];
        let args = []
        if(proxy != null && proxy != "null"){ // "null" means don't use any proxy
            args = ['--window-size=1920,1080', "--proxy-server=" + proxy]
        } else {
            args = [
                '--window-size=1920,1080',
                // Black magic to speed up crawling
                // https://github.com/puppeteer/puppeteer/issues/1718#issuecomment-397532083
                "--proxy-server='direct://'", '--proxy-bypass-list=*'
            ]
        }
        browsers[i] = await puppeteer.launch({
            handleSIGINT: false, // https://github.com/puppeteer/puppeteer/issues/5106#issuecomment-550496444
            headless: config.headless,
            // https://github.com/puppeteer/puppeteer/issues/1183
            defaultViewport: null,
            args: args
        });

        tabs[i] = [];
        uncrawledUrlSet[i] = new Set(crawlUrls[i]);
    }

    let crawl = async (browserId) => {
        return new Promise(async function(resolve, reject){
            for(let retry = 0; retry < config.retryTimes; retry ++){
                const crawlUrlList = Array.from(uncrawledUrlSet[browserId].values());
                log(`${logTime()} Browser ${browserId}: start retry ${retry}, list length ${crawlUrlList.length}`);

                if(crawlUrlList.length == 0)
                    break;
                uncrawledUrlSet[browserId].clear();

                if(retry != 0){
                    log(`${logTime()} Browser ${browserId}: sleep 5min before next retry`);
                    await new Promise(r => setTimeout(r, 5 * 60 * 1000)); // wayback machine seems to reset the counter after 5 minutes
                }

                for (let i = 0; i < crawlUrlList.length; i++) {
                    let url = crawlUrlList[i].url;
                    let original_domain = crawlUrlList[i].original_domain;

                    log(`${logTime()} Browser ${browserId}: `, "Progress", `${i}/${crawlUrlList.length}, retry ${retry}, `, url);

                    if(finished.has(url)){
                        log(`${logTime()} Has crawled ${url} (in finished list), pass.`);
                        continue;
                    }

                    if (tabs[browserId].length < tabNums) {
                        // Sleep to prevent burst traffic
                        tabs[browserId].push(browse(tabs[browserId].length, browserId, url, original_domain, tabs[browserId].length * (config.browseTimeMs / config.tabNum), retry))

                        continue;
                    }
                    let ret = await Promise.race(tabs[browserId]);
                    if(ret.hasError){
                        tabs[browserId][ret.tabId] = browse(ret.tabId, browserId, url, original_domain, 60 * 1000, retry);
                    }else{
                        tabs[browserId][ret.tabId] = browse(ret.tabId, browserId, url, original_domain, undefined, retry);
                    }
                }
                await Promise.all(tabs[browserId]);
            }

            log(`${logTime()} browser ${browserId} done, ${uncrawledUrlSet[browserId].size} url uncrawled, quitting this browser`);
            killBrowser(browserId);
            resolve(true);
        })
    }
    let promises = proxyList.map((proxy, index) => crawl(index));
    Promise.all(promises).then(() => {
        progressBar.stop();
        process.exit(0);
    });
}();
