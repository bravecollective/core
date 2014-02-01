/**
  * species.js - copyright @k33G_org
  * version 1.0
  * https://github.com/k33g/species
  * MIT License
  */

var Species = (function () {
    var species = {};

    species.Class = function(class_def) {
        var m, k, t;
        if(class_def.Extends) {
            k = Object.create(class_def.Extends);
            if(k.initialize) { k.initialize.prototype = k; }
            k.parent = class_def.Extends;
        } else {
            k = Object.create({});
        }

        /*--- define members ---*/
        for(m in class_def) {
            Object.defineProperty(k, m,{
                value : class_def[m],
                writable: true,
                enumerable: true,
                configurable: true
            });
        }

        /*--- if initialize is named ---*/
        Object.defineProperty(k, "typeName",{
            value : class_def["initialize"] ? class_def["initialize"].name.replace('_','') : null,
            writable: false,
            enumerable: true,
            configurable: false
        });

        /*--- isInstance ---*/
        Object.defineProperty(k, "isInstance",{
            value : false,
            writable: true,
            enumerable: true,
            configurable: true
        });

        /*--- isInstanceOf ---*/
        Object.defineProperty(k, "isInstanceOf",{
            value : function(klass) {
                if(this.isInstance){
                    return this.typeName == klass.typeName ? true : false;
                } else { return false; }

            },
            writable: false,
            enumerable: true,
            configurable: false
        });

        /*--- static ---*/
        if(k.Static) {
            for(var m in k.Static){
                Object.defineProperty(k, m,{
                    value : k.Static[m],
                    writable: true,
                    enumerable: true,
                    configurable: true
                });
            }
        }

        k.New = function(props) {
            var inst = Object.create(k),m;
            
            /*--- apply default values ---*/
            for(m in inst) { //default value
                if (typeof inst[m] != 'function') inst[m] = inst[m];
            }
            /*---*/

            inst.isInstance = true;
            if (inst.initialize) { inst.initialize.apply(inst, arguments); }

            /*--- static ---*/
            if(inst.Static) {
                for(var m in inst.Static){
                    inst[m] = undefined;
                }
                inst.Static = undefined;
            }
            return inst;
        }


        //function(){ throw 'static member'; };


        return k;
    };

    species.deSerialize = function(args) { //from : json_object, to : species_object
        //Species.deSerialize({ from : s, to : Z })
        //TODO : find doc about JSON.bind()
        var m, tmp = JSON.parse(args.from);
        for(m in tmp) {
            args.to[m] = tmp[m];
        }
        return args.to;
    };

    //only if you are not watching members
    species.serialize = function(species_object) {
        //TODO: to verifiy if watchable
        //TODO: remove instanceof, extend ...
        return JSON.stringify(species_object);
    }


    /*--- Watching ---*/
    species.watch = function(what, propertyName, handler) {
        what['watchable_'+propertyName] = what[propertyName];

        Object.defineProperty(what, propertyName,{
            get : function(){ return what['watchable_'+propertyName]; },
            set : function(value) {
                handler.call(what, { propertyName : propertyName, oldValue : what['watchable_'+propertyName], newValue : value });
                what['watchable_'+propertyName] = value;
            },
            enumerable: true,
            configurable: true
        });

    };

    /*--- UnWatching ---*/
    species.unwatch = function(what, propertyName) {
        var value = what[propertyName];
        delete what[propertyName]; // remove getter and setter
        delete what['watchable_'+propertyName];
        what[propertyName] = value;
    };

    species.unwatchAll = function(what) {
        //TODO: ...
    };

    /*--- AOP ---*/
    species.aop = {
        before : function(obj, fname, advice) {
            var oldFunc = obj[fname];
                obj[fname] = function() {
                advice.apply(this, arguments);
                return oldFunc.apply(this, arguments);
            }
        },
        after : function(obj, fname, advice) {
            var oldFunc = obj[fname];
            obj[fname] = function() {
                oldFunc.apply(this, arguments);
                return advice.apply(this, arguments);
            };
        }
    }


    return species;
}());