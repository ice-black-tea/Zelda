/**
 *  https://github.com/frida/frida-java-bridge/blob/main/lib/class-factory.js
 * 
 *  frida class
 *  └┬─ $classWrapper
 *   │  └─ className
 *   ├─ $getClassHandle
 *   ├─ constructor
 *   ├─ $dispose
 *   └─ $isSameObject
 *
 *  method class
 *  └┬─ methodName
 *   ├─ holder
 *   │  └─ className
 *   ├─ type
 *   ├─ handle
 *   ├─ implementation
 *   ├─ returnType
 *   ├─ argumentTypes
 *   └─ canInvokeWith
 */

/**
 *  用于方便调用frida的java方法
 */
export class JavaHelper {

    get classClass(): Java.Wrapper {
        return Java.use("java.lang.Class");
    }

    get stringClass(): Java.Wrapper {
        return Java.use("java.lang.String");
    }

    get threadClass(): Java.Wrapper {
        return Java.use("java.lang.Thread");
    }

    get throwableClass(): Java.Wrapper {
        return Java.use("java.lang.Throwable");
    }

    get uriClass(): Java.Wrapper {
        return Java.use("android.net.Uri");
    }

    get urlClass(): Java.Wrapper {
        return Java.use("java.net.URL");
    }

    get mapClass(): Java.Wrapper {
        return Java.use("java.util.Map");
    }

    get applicationContext(): Java.Wrapper {
        const activityThreadClass = Java.use('android.app.ActivityThread');
        return activityThreadClass.currentApplication().getApplicationContext();
    }

    isArray(obj: any): boolean {
        if (obj.hasOwnProperty("class") && obj.class instanceof Object) {
            if (obj.class.hasOwnProperty("isArray") && obj.class.isArray()) {
                return true;
            }
        }
        return false;
    }

    /**
     * 获取类对象类名
     * @param clazz 类对象
     * @returns 类名
     */
    getClassName<T extends Java.Members<T> = {}>(clazz: Java.Wrapper<T>): string {
        return clazz.$classWrapper.__name__;
    }

    /**
     * 获取java类的类对象
     * @param className java类名
     * @param classloader java类所在的ClassLoader
     * @returns 类对象
     */
    findClass<T extends Java.Members<T> = {}>(className: string, classloader: Java.Wrapper = void 0): Java.Wrapper<T> {
        if (classloader !== void 0 && classloader != null) {
            var originClassloader = Java.classFactory.loader;
            try {
                Reflect.set(Java.classFactory, "loader", classloader);
                return Java.use(className);
            } finally {
                Reflect.set(Java.classFactory, "loader", originClassloader);
            }
        } else {
            if (parseInt(Java.androidVersion) < 7) {
                return Java.use(className);
            }
            var error = null;
            var loaders = Java.enumerateClassLoadersSync();
            for (var i in loaders) {
                try {
                    var clazz = this.findClass<T>(className, loaders[i]);
                    if (clazz != null) {
                        return clazz;
                    }
                } catch (e) {
                    if (error == null) {
                        error = e;
                    }
                }
            }
            throw error;
        }
    }

    /**
     * 为method添加properties
     * @param method 方法对象
     */
    private $fixMethod<T extends Java.Members<T> = {}>(method: Java.Method<T>): void {
        Object.defineProperties(method, {
            className: {
                configurable: true,
                enumerable: true,
                get() {
                    return this.holder.$className || this.holder.__name__;
                },
            },
            name: {
                configurable: true,
                enumerable: true,
                get() {
                    const ret = this.returnType.className;
                    const name = this.className + "." + this.methodName;
                    let args = "";
                    if (this.argumentTypes.length > 0) {
                        args = this.argumentTypes[0].className;
                        for (let i = 1; i < this.argumentTypes.length; i++) {
                            args = args + ", " + this.argumentTypes[i].className;
                        }
                    }
                    return ret + " " + name + "(" + args + ")";
                }
            },
            toString: {
                value: function () {
                    return this.name;
                }
            }
        });
    }

    /**
     * hook指定方法对象
     * @param method 方法对象
     * @param impl hook实现，如调用原函数： function(obj, args) { return this(obj, args); }
     */
    private $hookMethod<T extends Java.Members<T> = {}>(method: Java.Method<T>, impl: (obj: Java.Wrapper<T>, args: any[]) => any = null): void {
        if (impl != null) {
            const proxy: Java.Method<T> = new Proxy(method, {
                apply: function (target, thisArg: any, argArray: any[]) {
                    const obj = argArray[0];
                    const args = argArray[1];
                    return target.apply(obj, args);
                }
            });
            method.implementation = function () {
                return impl.call(proxy, this, Array.prototype.slice.call(arguments));
            };
            Log.i("Hook method: " + method);
        } else {
            method.implementation = null;
            Log.i("Unhook method: " + method);
        }
    }

    /**
     * hook指定方法对象
     * @param clazz java类名/类对象
     * @param method java方法名/方法对象
     * @param signature java方法签名，为null表示不设置签名
     * @param impl hook实现，如调用原函数： function(obj, args) { return this(obj, args); }
     */
    hookMethod<T extends Java.Members<T> = {}>(
        clazz: string | Java.Wrapper<T>,
        method: string | Java.Method<T>,
        signatures: (string | Java.Wrapper<T>)[],
        impl: (obj: Java.Wrapper<T>, args: any[]) => any = null
    ): void {
        var tragetMethod: any = method;
        if (typeof (tragetMethod) === "string") {
            var targetClass: any = clazz;
            if (typeof (targetClass) === "string") {
                targetClass = this.findClass(targetClass);
            }
            tragetMethod = targetClass[tragetMethod];
            if (signatures != null) {
                var targetSignatures: any[] = signatures;
                for (var i in targetSignatures) {
                    if (typeof (targetSignatures[i]) !== "string") {
                        targetSignatures[i] = this.getClassName(targetSignatures[i]);
                    }
                }
                tragetMethod = tragetMethod.overload.apply(tragetMethod, targetSignatures);
            }
        }
        this.$fixMethod(tragetMethod);
        this.$hookMethod(tragetMethod, impl);
    }

    /**
     * hook指定方法名的所有重载
     * @param clazz java类名/类对象
     * @param method java方法名
     * @param impl hook实现，如调用原函数： function(obj, args) { return this(obj, args); }
     */
    hookMethods<T extends Java.Members<T> = {}>(
        clazz: string | Java.Wrapper<T>,
        methodName: string,
        impl: (obj: Java.Wrapper<T>, args: any[]) => any = null
    ): void {
        var targetClass: any = clazz;
        if (typeof (targetClass) === "string") {
            targetClass = this.findClass(targetClass);
        }
        var methods: Java.Method<T>[] = targetClass[methodName].overloads;
        for (var i = 0; i < methods.length; i++) {
            const targetMethod = methods[i];
            /* 过滤一些不存在的方法（拿不到返回值） */
            if (targetMethod.returnType !== void 0 &&
                targetMethod.returnType.className !== void 0) {
                this.$fixMethod(targetMethod);
                this.$hookMethod(targetMethod, impl);
            }
        }
    }

    /**
     * hook指定类的所有构造方法
     * @param clazz java类名/类对象
     * @param impl hook实现，如调用原函数： function(obj, args) { return this(obj, args); }
     */
    hookAllConstructors<T extends Java.Members<T> = {}>(
        clazz: string | Java.Wrapper<T>,
        impl: (obj: Java.Wrapper<T>, args: any[]) => any = null
    ): void {
        var targetClass: any = clazz;
        if (typeof (targetClass) === "string") {
            targetClass = this.findClass(targetClass);
        }
        this.hookMethods(targetClass, "$init", impl);
    }

    /**
     * hook指定类的所有成员方法
     * @param clazz java类名/类对象
     * @param impl hook实现，如调用原函数： function(obj, args) { return this(obj, args); }
     */
    hookAllMethods<T extends Java.Members<T> = {}>(
        clazz: string | Java.Wrapper<T>,
        impl: (obj: Java.Wrapper<T>, args: any[]) => any = null
    ): void {
        var targetClass: any = clazz;
        if (typeof (targetClass) === "string") {
            targetClass = this.findClass(targetClass);
        }
        var methodNames = [];
        var targetJavaClass = targetClass.class;
        while (targetJavaClass != null && targetJavaClass.getName() !== "java.lang.Object") {
            var methods = targetJavaClass.getDeclaredMethods();
            for (let i = 0; i < methods.length; i++) {
                const method = methods[i];
                var methodName = method.getName();
                if (methodNames.indexOf(methodName) < 0) {
                    methodNames.push(methodName);
                    this.hookMethods(targetClass, methodName, impl);
                }
            }
            targetJavaClass = Java.cast(targetJavaClass.getSuperclass(), this.classClass);
        }
    }

    /**
     * hook指定类的所有方法（构造、成员方法）
     * @param clazz java类名/类对象
     * @param impl hook实现，如调用原函数： function(obj, args) { return this(obj, args); }
     */
    hookClass<T extends Java.Members<T> = {}>(
        clazz: string | Java.Wrapper<T>,
        impl: (obj: Java.Wrapper<T>, args: any[]) => any = null
    ): void {
        var targetClass: any = clazz;
        if (typeof (targetClass) === "string") {
            targetClass = this.findClass(targetClass);
        }
        this.hookAllConstructors(targetClass, impl);
        this.hookAllMethods(targetClass, impl);
    }

    /**
     * 根据当前栈调用原java方法
     * @param obj java对象
     * @param args java参数
     * @returns java方法返回值
     */
    callMethod<T extends Java.Members<T> = {}>(obj: Java.Wrapper<T>, args: any[]): any {
        var methodName = this.getStackTrace()[0].getMethodName();
        if (methodName === "<init>") {
            methodName = "$init";
        }
        return Reflect.get(obj, methodName).apply(obj, args);
    }

    /**
     * 获取hook实现，调用原方法并发送调用事件
     * @param options hook选项，如：{stack: true, args: true, thread: true}
     * @returns hook实现
     */
    getEventImpl<T extends Java.Members<T> = {}>(options: any): (obj: Java.Wrapper<T>, args: any[]) => any {
        const javaHelperThis = this;

        const opts = new function() {
            this.method = true;
            this.thread = false;
            this.stack = false;
            this.args = false;
            this.extras = {};
            for (const key in options) {
                if (key in this) {
                    this[key] = options[key];
                } else {
                    this.extras[key] = options[key];
                }
            }
        };

        return function (obj, args) {
            const result = this(obj, args);
            const event = {};
            for (const key in opts.extras) {
                event[key] = opts.extras[key];
            }
            if (opts.method) {
                event["class_name"] = obj.$className;
                event["method_name"] = this.name;
                event["method_simple_name"] = this.methodName;
            }
            if (opts.thread) {
                event["thread_id"] = Process.getCurrentThreadId();
                event["thread_name"] = javaHelperThis.threadClass.currentThread().getName();
            }
            if (opts.args) {
                event["args"] = pretty2Json(args);
                event["result"] = pretty2Json(result);
            }
            if (opts.stack) {
                event["stack"] = pretty2Json(javaHelperThis.getStackTrace());
            }
            send({
                event: event
            });
            return result;
        };
    }

    /**
     * java数组转为js数组
     * @param clazz java类名/类对象
     * @param array java数组
     * @returns js数组
     */
    fromJavaArray<T extends Java.Members<T> = {}>(
        clazz: string | Java.Wrapper<T>,
        array: Java.Wrapper<T>
    ): Java.Wrapper<T>[] {
        var targetClass: any = clazz;
        if (typeof (targetClass) === "string") {
            targetClass = this.findClass(targetClass);
        }
        var result = [];
        var env = Java.vm.getEnv();
        for (var i = 0; i < env.getArrayLength(array.$handle); i++) {
            result.push(Java.cast(env.getObjectArrayElement(array.$handle, i), targetClass))
        }
        return result;
    }

    /**
     * 获取枚举值
     * @param clazz java类名/类对象
     * @param name java枚举名称
     * @returns java枚举值
     */
    getEnumValue<T extends Java.Members<T> = {}>(
        clazz: string | Java.Wrapper<T>,
        name: string
    ): Java.Wrapper<T> {
        var targetClass: any = clazz;
        if (typeof (targetClass) === "string") {
            targetClass = this.findClass(targetClass);
        }
        var values = targetClass.class.getEnumConstants();
        if (!(values instanceof Array)) {
            values = this.fromJavaArray(targetClass, values);
        }
        for (var i = 0; i < values.length; i++) {
            if (values[i].toString() === name) {
                return values[i];
            }
        }
        throw new Error("Name of " + name + " does not match " + targetClass);
    }

    /**
     * 获取当前java栈
     * @param printStack 是否展示栈，默认为true
     * @param printArgs 是否展示参数，默认为true
     * @returns java栈对象
     */
    getStackTrace<T extends Java.Members<T> = {}>(): Java.Wrapper<T>[] {
        const result = [];
        const elements = this.throwableClass.$new().getStackTrace();
        for (let i = 0; i < elements.length; i++) {
            result.push(elements[i]);
        }
        return result;
    }

    private $makeStackObject<T extends Java.Members<T> = {}>(elements: Java.Wrapper<T>[] = void 0) {
        if (elements === void 0) {
            elements = this.getStackTrace()
        }
        var body = "Stack: ";
        for (var i = 0; i < elements.length; i++) {
            body += "\n    at " + pretty2String(elements[i]);
        }
        return { "stack": body };
    }

    /**
     * 打印当前栈
     */
    printStack(): void {
        var elements = this.getStackTrace();
        Log.i(this.$makeStackObject(elements));
    }

    private $makeArgsObject(args: any, ret: any) {
        var body = "Arguments: ";
        for (var i = 0; i < args.length; i++) {
            body += "\n    Arguments[" + i + "]: " + pretty2String(args[i]);
        }
        if (ret !== void 0) {
            body += "\n    Return: " + pretty2String(ret);
        }
        return { "arguments": body };
    }

    /**
     * 打印当前参数和返回值
     * @param args java方法参数
     * @param ret java方法返回值
     * @param message 回显的信息
     */
    printArguments(args: any, ret: any) {
        Log.i(this.$makeArgsObject(args, ret));
    }

}