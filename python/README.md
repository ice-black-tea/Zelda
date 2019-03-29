# Android Tools

## frida

### 方法1：运行frida hook脚本

如hook.py：
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from android_tools.frida import FridaHelper

jscode = """
Java.perform(function () {
    var Clazz = Java.use("java.lang.Class");
    var HashMap = Java.use("java.util.HashMap");

    HashMap.put.implementation = function() {

        send("this.threshold = " + this.threshold.value);

        var clazz = Java.cast(this.getClass(), Clazz);
        var field = clazz.getDeclaredField("threshold");
        field.setAccessible(true);
        send("this.threshold = " + field.getInt(this));

        // call origin method
        var ret = callMethod(this, arguments);
        printStack();
        printArgsAndReturn(null, arguments, ret);
        return ret;
    }
});
"""

if __name__ == '__main__':
    FridaHelper().run_script("xxx.xxx.xxx", jscode=jscode)
    sys.stdin.read()
```


### 方法2：使用at_frida

注入js文件或js代码到指定进程，支持下载server，打开server，js文件实时加载，应用重启后注入等功能

```bash
$ at_frida.py -h
usage: at_frida.py [-h] [-v] [-s SERIAL] [-p PACKAGE] (-f FILE | -c CODE) [-r]

easy to use frida

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -s SERIAL, --serial SERIAL
                        use device with given serial
  -p PACKAGE, --package PACKAGE
                        target package [default top-level package]
  -f FILE, --file FILE  javascript file
  -c CODE, --code CODE  javascript code
  -r, --restart         inject after restart [default false]
```

如hook.js文件：
```javascript

Java.perform(function () {

    // 1: hook all put methods of HashMap class
    // same as hookMethods("java.util.HashMap", "put", getHookFn(true /* print stack */, true /* print args */));
    hookMethods("java.util.HashMap", "put", function(method, obj, args) {
        var ret = method.apply(obj, args);
        printStack(method);
        printArgsAndReturn(method, args, ret);
        return ret;
    });
    
    // 2: hook all methods of HashMap class
    hookClass("java.util.HashMap", getHookFn(true /* print stack */, true /* print args */));

    // 3: hook put method of HashMap class
    var HashMap = Java.use("java.util.HashMap");
    HashMap.put.implementation = function() {
        var ret = callMethod(this, arguments);
        printStack(null);
        printArgsAndReturn(null, arguments, ret);
        return ret;
    }
});
```

在终端中运行
```bash
at_frida.py -f hook.js
```

### 输出效果

![frida](imgs/frida.png)


### js使用

内置的js函数

```javascript
/*
 * byte数组转字符串，如果转不了就会抛异常
 * :param bytes:       字符数组
 * :param charset:     字符集(可选)
 */
function BytesToString(bytes, charset);

/*
 * 输出当前调用堆栈
 */
function PrintStack();

/*
 * 调用当前函数，并输出参数返回值
 * :param object:      对象(一般直接填this)
 * :param arguments:   arguments(固定填这个)
 * :param showStack:   是否打印栈(默认为false，可不填)
 * :param showArgs:    是否打印参数(默认为false，可不填)
 */
function CallMethod(object, arguments, showStack, showArgs);

/*
 * 打印栈，调用当前函数，并输出参数返回值
 * :param object:      对象(一般直接填this)
 * :param arguments:   arguments(固定填这个)
 * :param showStack:   是否打印栈(默认为true，可不填)
 * :param showArgs:    是否打印参数(默认为true，可不填)
 */
function PrintStackAndCallMethod(object, arguments, showStack, showArgs);
```

hook native方法
```javascript
// xxxxxx为方法名
Interceptor.attach(Module.findExportByName(null, 'xxxxxx'), {
    onEnter: function (args) {
        send("xxxxxx called from:\\n" +
            Thread.backtrace(this.context, Backtracer.ACCURATE)
                .map(DebugSymbol.fromAddress).join("\\n"));
    },
    onLeave: function (retval) {
        send("xxxxxx retval: " + retval);
    }
});
```

调用native方法
```javascript
// 如 CallStack callStack("ABCDEFG", 10);
var CallStackPtr = Module.findExportByName(null, '_ZN7android9CallStackC1EPKci');
var CallStack = new NativeFunction(CallStackPtr, 'pointer', ['pointer', 'pointer', 'int']);
var callStack = Memory.alloc(1000);
var logtag = Memory.allocUtf8String("ABCDEFG");
CallStack(callStack, logtag, 10);
```

## at_top_app

显示顶层应用信息、获取顶层应用apk、截屏等

```bash
$ at_top_app.py -h
usage: at_top_app.py [-h] [-v] [-s SERIAL]
                     [--package | --activity | --path | --apk [path] |
                     --screen [path]]

show top-level app's basic information

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -s SERIAL, --serial SERIAL
                        use device with given serial
  --package             show top-level package name
  --activity            show top-level activity name
  --path                show top-level package path
  --apk [path]          pull top-level apk file
  --screen [path]       capture screen and pull file
```

## at_intent

打开设置界面、开发者选项界面、app设置界面、安装证书、打开浏览器链接等

```bash
$ at_intent.py -h
usage: at_intent.py [-h] [-v] [-s SERIAL]
                    (--setting | --setting-dev | --setting-dev2 | --setting-app [PACKAGE] | --setting-cert PATH | --browser URL)

common intent action

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -s SERIAL, --serial SERIAL
                        use device with given serial
  --setting             start setting activity
  --setting-dev         start development setting activity
  --setting-dev2        start development setting activity
  --setting-app [PACKAGE]
                        start application setting activity [default top-level
                        package]
  --setting-cert PATH   start cert installer activity and install cert (need
                        '/data/local/tmp' write permission)
  --browser URL         start browser activity and jump to url (need scheme,
                        such as https://antiy.cn)
```

## at_grep

正则匹配文件内容（含zip文件内容）

```bash
$ at_grep.py -h
usage: at_grep.py [-h] [-v] [-i] pattern [file [file ...]]

match files with regular expressions

positional arguments:
  pattern            regular expression
  file               target files path

optional arguments:
  -h, --help         show this help message and exit
  -v, --version      show program's version number and exit
  -i, --ignore-case  ignore case
```

## at_app

展示app基本信息

```bash
$ at_app.py -h
usage: at_app.py [-h] [-v] [-s SERIAL] (-a | -t | -p pkg [pkg ...])
                 [-o field [field ...]]

fetch application info

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -s SERIAL, --serial SERIAL
                        use device with given serial
  -a, --all             fetch all apps
  -t, --top             fetch top-level app only
  -p pkg [pkg ...], --packages pkg [pkg ...]
                        fetch target apps
  -o field [field ...], --order-by field [field ...]
                        order by target field
```

### 输出效果

![apps](imgs/apps.png)

## at_tools

读取[配置文件](android_tools/resource/config/tools.json)，下载使用对应工具

```bash
$ at_tools.py 
usage: at_tools.py [-h]
                   {adb,apktool,baksmali,compact_dex_converter,fastboot,java,mipay_extract,smali,vdex_extractor}
```


## at_call_dex

测试android-tools.dex时使用