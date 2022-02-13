
////////////////////////////////////////////////////////////////////////
// log
////////////////////////////////////////////////////////////////////////

class Log {

    debug = 1;
    info = 2;
    warning = 3;
    error = 4;
    private $level = this.info;

    get level(): number {
        return this.$level;
    }

    setLevel(level: number) {
        this.$level = level;
        this.d("Set log level: " + level);
    }

    d(data: any, tag: string = null) {
        if (this.$level <= this.debug) {
            send({ log: { level: "debug", tag: tag, message: data } });
        }
    }

    i(data: any, tag: string = null) {
        if (this.$level <= this.info) {
            send({ log: { level: "info", tag: tag, message: data } });
        }
    }

    w(data: any, tag: string = null) {
        if (this.$level <= this.warning) {
            send({ log: { level: "warning", tag: tag, message: data } });
        }
    }

    e(data: any, tag: string = null) {
        if (this.$level <= this.error) {
            send({ log: { level: "error", tag: tag, message: data } });
        }
    }
}


////////////////////////////////////////////////////////////////////////
// script loader
////////////////////////////////////////////////////////////////////////

interface Parameters {
    [name: string]: any;
}

interface Script {
    filename: string;
    source: string;
}

class ScriptLoader {

    load(scripts: Script[], parameters: Parameters) {
        Object.defineProperties(globalThis, {
            parameters: {
                enumerable: true,
                value: parameters
            }
        });

        for (const script of scripts) {
            try {
                (1, eval)(script.source);
            } catch (e) {
                throw new Error(`Unable to load ${script.filename}: ${e.stack}`);
            }
        }
    }
}

const loader = new ScriptLoader();

rpc.exports = {
    loadScripts: loader.load.bind(loader),
};


////////////////////////////////////////////////////////////////////////
// global variables
////////////////////////////////////////////////////////////////////////

import { CHelper } from "./lib/c"
import { JavaHelper } from "./lib/java";
import { AndroidHelper } from "./lib/android";
import { ObjCHelper } from "./lib/objc";


const log = new Log();
const cHelper = new CHelper();
const javaHelper = new JavaHelper();
const androidHelper = new AndroidHelper();
const objCHelper = new ObjCHelper();


declare global {
    const Log: Log;
    const CHelper: CHelper;
    const JavaHelper: JavaHelper;
    const AndroidHelper: AndroidHelper;
    const ObjCHelper: ObjCHelper;
    const parameters: Parameters;
    function memoize(): Function;
    function ignoreError<T>(fn: () => T, defautValue: T): T;
    function pretty2String(obj: any): any;
    function pretty2Json(obj: any): any;
}


Object.defineProperties(globalThis, {
    Log: {
        enumerable: true,
        value: log
    },
    CHelper: {
        enumerable: true,
        value: cHelper
    },
    JavaHelper: {
        enumerable: true,
        value: javaHelper
    },
    AndroidHelper: {
        enumerable: true,
        value: androidHelper
    },
    ObjCHelper: {
        enumerable: true,
        value: objCHelper
    },
    ignoreError: {
        enumerable: false,
        value: function <T>(fn: () => T, defautValue: T = undefined): T {
            try {
                return fn();
            } catch (e) {
                log.d("Catch ignored error. " + e);
                return defautValue;
            }
        }
    },
    pretty2String: {
        enumerable: false,
        value: function (obj: any): string {
            obj = pretty2Json(obj);
            return obj instanceof Object ? JSON.stringify(obj) : obj;
        }
    },
    pretty2Json: {
        enumerable: false,
        value: function (obj: any): any {
            if (!(obj instanceof Object)) {
                return obj;
            }
            if (Array.isArray(obj) || javaHelper.isArray(obj)) {
                let result = [];
                for (let i = 0; i < obj.length; i++) {
                    result.push(pretty2Json(obj[i]));
                }
                return result;
            }
            return ignoreError(() => obj.toString(), void 0);
        }
    }
});
