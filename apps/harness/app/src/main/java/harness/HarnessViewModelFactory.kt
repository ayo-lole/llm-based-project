package harness

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import java.lang.reflect.Proxy
import kotlin.reflect.KClass
import kotlin.reflect.full.primaryConstructor
import kotlin.reflect.jvm.isAccessible
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow

class HarnessViewModelFactory : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        val kClass = modelClass.kotlin
        val ctor = kClass.primaryConstructor
        if (ctor == null) {
            return modelClass.getDeclaredConstructor().newInstance()
        }
        ctor.isAccessible = true
        val args = ctor.parameters.map { param ->
            val classifier = param.type.classifier as? KClass<*>
            val javaCls = classifier?.java
            when {
                classifier == SavedStateHandle::class -> SavedStateHandle()
                javaCls != null && Flow::class.java.isAssignableFrom(javaCls) -> emptyFlow<Any>()
                javaCls != null && javaCls.isInterface -> proxyFor(javaCls)
                classifier == String::class -> ""
                classifier == Int::class || classifier == Integer::class -> 0
                classifier == Long::class || classifier == java.lang.Long::class -> 0L
                classifier == Boolean::class || classifier == java.lang.Boolean::class -> false
                classifier == Float::class || classifier == java.lang.Float::class -> 0f
                classifier == Double::class || classifier == java.lang.Double::class -> 0.0
                param.type.isMarkedNullable -> null
                javaCls != null -> noArgOrNull(javaCls)
                else -> null
            }
        }
        return ctor.call(*args.toTypedArray()) as T
    }

    private fun noArgOrNull(cls: Class<*>): Any? {
        return try {
            cls.getDeclaredConstructor().newInstance()
        } catch (_: Exception) {
            null
        }
    }

    private fun proxyFor(iface: Class<*>): Any {
        return Proxy.newProxyInstance(
            iface.classLoader,
            arrayOf(iface),
        ) { _, method, _ ->
            val rt = method.returnType
            when {
                rt == java.lang.Void.TYPE -> null
                Flow::class.java.isAssignableFrom(rt) -> emptyFlow<Any>()
                rt == java.lang.Boolean.TYPE || rt == java.lang.Boolean::class.java -> false
                rt == Integer.TYPE || rt == Integer::class.java -> 0
                rt == java.lang.Long.TYPE || rt == java.lang.Long::class.java -> 0L
                rt == java.lang.Float.TYPE || rt == java.lang.Float::class.java -> 0f
                rt == java.lang.Double.TYPE || rt == java.lang.Double::class.java -> 0.0
                Collection::class.java.isAssignableFrom(rt) -> emptyList<Any>()
                rt == String::class.java -> ""
                else -> null
            }
        }
    }
}
