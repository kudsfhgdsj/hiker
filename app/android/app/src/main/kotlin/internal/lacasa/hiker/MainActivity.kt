package internal.lacasa.hiker

import android.os.Handler
import android.os.Looper
import btools.router.OsmNodeNamed
import btools.router.RoutingContext
import btools.router.RoutingEngine
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {
    // Routing takes a moment and must not block the user interface.
    private val routing = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "hiker/routing")
            .setMethodCallHandler { call, result ->
                if (call.method == "route") route(call, result) else result.notImplemented()
            }
    }

    /**
     * A route along paths, computed on the device by BRouter from the path data in
     * `segments`. Answers with a flat list of latitude, longitude and elevation per point
     * (NaN where the elevation is unknown), or with the error `no_route`.
     */
    private fun route(call: MethodCall, result: MethodChannel.Result) {
        val segments = call.argument<String>("segments")!!
        val profile = call.argument<String>("profile")!!
        val points = call.argument<List<List<Double>>>("points")!!
        val parameters = call.argument<Map<String, String>>("parameters") ?: emptyMap()
        val timeoutMs = (call.argument<Number>("timeoutMs") ?: 25000).toLong()
        routing.execute {
            try {
                val waypoints = points.mapIndexed { index, point ->
                    OsmNodeNamed().apply {
                        name = when (index) {
                            0 -> "from"
                            points.lastIndex -> "to"
                            else -> "via$index"
                        }
                        ilat = ((point[0] + 90.0) * 1e6 + 0.5).toInt()
                        ilon = ((point[1] + 180.0) * 1e6 + 0.5).toInt()
                    }
                }
                val context = RoutingContext().apply {
                    // lookups.dat lies next to the profile.
                    localFunction = profile
                    keyValues = HashMap(parameters)
                }
                val engine = RoutingEngine(null, null, File(segments), waypoints, context)
                engine.quite = true
                engine.doRun(timeoutMs)
                val track = engine.foundTrack
                val error = engine.errorMessage
                if (error != null || track == null || track.nodes.size < 2) {
                    main.post { result.error("no_route", error ?: "no route", null) }
                    return@execute
                }
                val line = DoubleArray(track.nodes.size * 3)
                track.nodes.forEachIndexed { index, node ->
                    line[index * 3] = node.iLat / 1e6 - 90.0
                    line[index * 3 + 1] = node.iLon / 1e6 - 180.0
                    line[index * 3 + 2] =
                        if (node.sElev == Short.MIN_VALUE) Double.NaN else node.elev
                }
                main.post { result.success(line) }
            } catch (error: Throwable) {
                // Also OutOfMemoryError: a route that is too long must not take the app down.
                main.post { result.error("routing_failed", error.toString(), null) }
            }
        }
    }

    override fun onDestroy() {
        routing.shutdown()
        super.onDestroy()
    }
}
