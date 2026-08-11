# -*- coding: utf-8 -*-
"""Pruebas del nuevo orden de calculo de las divisorias (core/divides.py).

Se prueban las funciones de perfil y de recorte, que son las que deciden la
forma. Las que recorren capas se validan en QGIS sobre el caso real.
"""
import importlib.util
import math
import os
import sys
import types

_q = types.ModuleType("qgis")
_c = types.ModuleType("qgis.core")


def _cualquier_clase(nombre):
    if nombre.startswith("_"):
        raise AttributeError(nombre)
    cls = type(nombre, (), {})
    setattr(_c, nombre, cls)
    return cls


_c.__getattr__ = _cualquier_clase
_q.core = _c
sys.modules.setdefault("qgis", _q)
sys.modules.setdefault("qgis.core", _c)

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "geomorphic_reclamation_designer", "core")
_ruta = os.path.join(_DIR, "divides.py")
_src = open(_ruta, encoding="utf-8").read().replace(
    "from .compat import attrs, indices_datos",
    "attrs = lambda capa, v: v\nindices_datos = lambda capa: []").replace(
    "from .ridges import convexo_cresta", "convexo_cresta = None")
dv = types.ModuleType("gfq_divides")
exec(compile(_src, _ruta, "exec"), dv.__dict__)


# ------------------------------------------------------------- proyeccion
def test_proyeccion_da_estacion_y_cota():
    dens = [(0.0, 0.0, 100.0), (100.0, 0.0, 200.0)]
    d, s, z = dv._proyectar(dens, 30.0, 4.0)
    assert abs(d - 4.0) < 1e-9
    assert abs(s - 30.0) < 1e-9
    assert abs(z - 130.0) < 1e-9


def test_puntos_de_control_se_queda_con_la_cabecera_mas_alta():
    """Dos espolones que llegan a la misma estacion: manda el mas alto, porque
    la divisoria no puede quedar por debajo de ninguno de los dos."""
    dens = [(0.0, 0.0), (100.0, 0.0)]
    cab = [(50.0, 2.0, 120.0), (50.0, -2.0, 125.0), (10.0, 1.0, 110.0),
           (50.0, 40.0, 999.0)]          # este esta lejos: se descarta
    ctrl = dv.puntos_de_control(dens, cab, tol=12.0)
    assert ctrl == [(10.0, 110.0), (50.0, 125.0)]


def test_dos_cabeceras_pegadas_se_funden_en_la_mas_alta():
    """B-036. La divisoria tiene los vertices a 2-3 m: dos cabeceras separadas
    metro y medio caen sobre el mismo vertice o sobre vecinos, y obligarla a
    pasar por las dos escribe un escalon donde deberia haber pendiente."""
    dens = [(0.0, 0.0), (100.0, 0.0)]
    cab = [(50.0, 0.0, 120.0), (51.5, 0.0, 126.0), (80.0, 0.0, 130.0)]
    ctrl = dv.puntos_de_control(dens, cab, tol=12.0)
    assert ctrl == [(51.5, 126.0), (80.0, 130.0)]


def test_las_cabeceras_no_se_funden_en_cadena():
    """Una hilera separada algo menos que la ventana no puede irse encadenando
    hasta fundir media divisoria en un solo punto: la ventana se mide contra el
    arranque del grupo."""
    dens = [(0.0, 0.0), (100.0, 0.0)]
    cab = [(x, 0.0, 100.0 + x) for x in (10.0, 14.0, 18.0, 22.0, 26.0)]
    ctrl = dv.puntos_de_control(dens, cab, tol=12.0, separacion=5.0)
    # tres grupos (10-14, 18-22, 26) y no uno solo; de cada grupo se queda la
    # mas alta, EN SU PROPIA ESTACION, que es donde tiene que caer
    assert ctrl == [(14.0, 114.0), (22.0, 122.0), (26.0, 126.0)]


# --------------------------------------------------------------- perfil
def _dens_recta(n=21, paso=5.0):
    return [(i * paso, 0.0) for i in range(n)]


def _base_lineal(dens, z0, z1):
    n = len(dens)
    return [z0 + (z1 - z0) * i / (n - 1) for i in range(n)]


def test_el_perfil_pasa_exactamente_por_los_puntos_de_control():
    """Es la condicion que hace que las subcrestas mueran sobre la divisoria
    sin escalon: la cota de la divisoria en la estacion de la cabecera tiene
    que ser la de la cabecera."""
    dens = _dens_recta()
    base = _base_lineal(dens, 1060.0, 1090.0)
    ctrl = [(25.0, 1078.0), (50.0, 1080.0)]
    zs = dv.perfil_desde_control(dens, base, ctrl, s_max=1.0)
    s = dv._estaciones(dens)
    for sc, zc in ctrl:
        i = min(range(len(s)), key=lambda k: abs(s[k] - sc))
        assert abs(zs[i] - zc) < 1e-6, (sc, zc, zs[i])


def test_lejos_de_los_espolones_se_conserva_el_perfil_de_diseno():
    """Lo que hacia falta: con dos cabeceras en 180 m, el extremo truncado no
    puede quedarse trece metros por encima de donde toca. Fuera del alcance de
    la correccion la divisoria es la de diseno."""
    dens = _dens_recta(41, 5.0)              # 200 m
    base = _base_lineal(dens, 1134.0, 1063.0)
    ctrl = [(20.0, 1120.0)]                  # un espolon, cerca del inicio
    zs = dv.perfil_desde_control(dens, base, ctrl, s_max=1.0)
    assert abs(zs[-1] - base[-1]) < 1e-6     # el extremo lejano no se mueve
    i = min(range(len(dens)), key=lambda k: abs(dv._estaciones(dens)[k] - 20.0))
    assert abs(zs[i] - 1120.0) < 1e-6        # el espolon si manda donde esta


def test_la_correccion_se_apaga_de_forma_gradual():
    dens = _dens_recta(41, 5.0)
    base = _base_lineal(dens, 1100.0, 1060.0)
    zs = dv.perfil_desde_control(dens, base, [(100.0, 1085.0)], s_max=1.0)
    s = dv._estaciones(dens)
    resid = [z - b for z, b in zip(zs, base)]
    i100 = min(range(len(s)), key=lambda k: abs(s[k] - 100.0))
    assert abs(resid[i100] - 5.0) < 1e-6
    assert abs(resid[0]) < 1e-6 and abs(resid[-1]) < 1e-6
    # decae de forma monotona a cada lado
    izq = resid[:i100 + 1]
    assert izq == sorted(izq)


def test_perfil_monotono_aunque_el_control_tenga_un_diente():
    dens = _dens_recta()
    base = _base_lineal(dens, 1060.0, 1090.0)
    ctrl = [(40.0, 1085.0), (60.0, 1070.0)]
    zs = dv.perfil_desde_control(dens, base, ctrl, s_max=1.0, monotona=True)
    # el control se respeta, pero el resto no puede quedar por encima del diente
    s = dv._estaciones(dens)
    i = min(range(len(s)), key=lambda k: abs(s[k] - 40.0))
    assert abs(zs[i] - 1085.0) < 1e-6


def test_el_filo_no_se_limita_con_la_pendiente_de_ladera():
    """'Maximum straight-line slopes' habla de la pendiente de cresta a canal,
    NO del perfil longitudinal del filo de una divisoria. La del original
    desciende 73 m en 178 (41 % de media, con tramos al 73 %); limitarla al
    33 % la dejaba 17 m colgada sobre el cauce. Solo se aplica un cortafuegos
    contra picos imposibles."""
    dens = _dens_recta(36, 5.0)                       # 175 m
    base = _base_lineal(dens, 1134.0, 1061.0)         # 42 % de media
    zs = dv.perfil_desde_control(dens, base, [(20.0, 1120.0)], s_max=0.33)
    assert abs(zs[-1] - 1061.0) < 0.5, zs[-1]         # llega abajo, no se cuelga
    s = dv._estaciones(dens)
    peor = max(abs(zs[i + 1] - zs[i]) / (s[i + 1] - s[i])
               for i in range(len(zs) - 1))
    assert peor <= dv.MAX_PENDIENTE_FILO + 1e-9


def test_el_cortafuegos_recorta_un_pico_imposible():
    dens = _dens_recta(11, 5.0)
    base = [1000.0] * 5 + [1200.0] + [1000.0] * 5     # pico de 200 m
    zs = dv.perfil_desde_control(dens, base, [(0.0, 1000.0)], s_max=0.33,
                                 monotona=False)
    s = dv._estaciones(dens)
    peor = max(abs(zs[i + 1] - zs[i]) / (s[i + 1] - s[i])
               for i in range(len(zs) - 1))
    assert peor <= dv.MAX_PENDIENTE_FILO + 1e-9


def test_un_control_inalcanzable_se_recorta_sin_dejar_pico():
    """Si una cabecera pide una cota que ni el cortafuegos de pendiente
    permite, se recorta: dejarla intacta metia un pico de 200 % en el filo. El
    empalme no se pierde, porque el paso siguiente vuelve a pegar la cabecera a
    la cota que la divisoria tenga finalmente."""
    dens = _dens_recta()
    base = _base_lineal(dens, 1060.0, 1090.0)
    zs = dv.perfil_desde_control(dens, base, [(50.0, 1200.0)], s_max=0.33)
    s = dv._estaciones(dens)
    peor = max(abs(zs[i + 1] - zs[i]) / (s[i + 1] - s[i])
               for i in range(len(zs) - 1))
    assert peor <= dv.MAX_PENDIENTE_FILO + 1e-9, peor
    i = min(range(len(s)), key=lambda k: abs(s[k] - 50.0))
    assert zs[i] > base[i]           # la cabecera si levanta la divisoria...
    assert zs[i] < 1200.0            # ...pero no hasta lo imposible


def test_una_loma_con_el_extremo_anclado_abajo_no_deja_meseta_ni_acantilado():
    """B-036, el caso real: divisoria fid=52 del Ej_2.

    Arranca a 289 con cuatro cabeceras pegadas, sube a 297 en el centro y su
    otro extremo esta anclado a 276 contra el cauce. Como 276 < 289, la
    monotonia global la declaraba DESCENDENTE: aplanaba los primeros 48 m en
    una meseta de 28 vertices exactamente a 289.31, dejaba el perfil encaramado
    a 297 detras del control y soltaba los 21 m que faltaban en cuatro
    segmentos al 100 % clavado."""
    dens = [(2.8 * i, 0.0) for i in range(42)]          # 114.8 m
    s = dv._estaciones(dens)
    L = s[-1]
    base = [289.31 + (276.0 - 289.31) * (si / L) for si in s]
    ctrl = [(4.7, 289.31), (62.7, 297.09)]
    zs = dv.perfil_desde_control(dens, base, ctrl, s_max=0.33,
                                 z_top=276.0, z_bot=289.31)

    pend = [abs(zs[i + 1] - zs[i]) / (s[i + 1] - s[i]) for i in range(len(zs) - 1)]
    assert max(pend) < dv.MAX_PENDIENTE_FILO - 1e-6, \
        "el filo vuelve a apoyarse en el cortafuegos: %.3f" % max(pend)

    i = min(range(len(s)), key=lambda k: abs(s[k] - 62.7))
    assert zs[i] > zs[0] and zs[i] > zs[-1], "la loma tiene que sobrevivir"

    # Detras de la corona no puede quedar ni un tramo llano: ahi es donde el
    # trinquete dejaba la meseta. Delante si puede haberlo, porque el anclaje
    # (289.31) y la primera cabecera (289.31) piden la MISMA cota y entre dos
    # cotas iguales lo llano es lo correcto.
    llano = mayor = 1
    for k in range(i + 1, len(zs)):
        llano = llano + 1 if abs(zs[k] - zs[k - 1]) <= 0.01 else 1
        mayor = max(mayor, llano)
    assert mayor <= 2, "meseta de %d vertices detras de la corona" % mayor


def _vaiven(zs):
    sube = sum(max(0.0, zs[i + 1] - zs[i]) for i in range(len(zs) - 1))
    baja = sum(max(0.0, zs[i] - zs[i + 1]) for i in range(len(zs) - 1))
    return sube + baja - abs(zs[0] - zs[-1])


def test_una_silla_cabe_sin_soltar_el_resto_del_perfil():
    """La monotonia por tramos de B-036 admite una silla de forma nativa: la
    silla es uno de los puntos fijos, asi que el hoyo cabe —se baja hasta el y
    se sube despues— sin tener que soltar la linea entera.

    El motor todavia la apaga cuando hay sillas (`monotona = (n_sillas == 0)`,
    ver P-24); esta prueba fija el comportamiento de la funcion, que es lo que
    permitira quitar ese apagado cuando toque."""
    dens = _dens_recta(61, 5.0)                       # 300 m
    base = _base_lineal(dens, 1000.0, 1060.0)         # sube 60 m
    ctrl = [(50.0, 1012.0), (150.0, 1028.0), (250.0, 1050.0)]
    silla = (200.0, 1033.0)                           # hoyo: por debajo de 1050
    zs = dv.perfil_desde_control(dens, base, sorted(ctrl + [silla]),
                                 s_max=0.33, monotona=True)
    s = dv._estaciones(dens)

    def en(sc):
        return zs[min(range(len(s)), key=lambda k: abs(s[k] - sc))]

    # el hoyo esta, y esta por debajo de los dos controles que lo rodean
    assert en(200.0) < en(150.0) or en(200.0) < en(250.0), "la silla se perdio"

    # ...y el resto del perfil NO se ha soltado: el vaiven es el que piden los
    # propios controles, sin invenciones
    pedido = _vaiven([1012.0, 1028.0, 1033.0, 1050.0])
    assert _vaiven(zs) <= pedido + 1.0, \
        "vaiven %.2f m frente a los %.2f m que piden los controles" % (
            _vaiven(zs), pedido)


def test_anclaje_del_extremo_en_el_limite():
    dens = _dens_recta()
    base = _base_lineal(dens, 1060.0, 1090.0)
    zs = dv.perfil_desde_control(dens, base, [(50.0, 1075.0)], s_max=1.0,
                                 z_top=1092.0, z_bot=1057.0)
    assert abs(zs[0] - 1057.0) < 1e-6 and abs(zs[-1] - 1092.0) < 1e-6


def test_sin_puntos_de_control_no_toca_el_perfil():
    dens = _dens_recta()
    base = _base_lineal(dens, 1060.0, 1090.0)
    assert dv.perfil_desde_control(dens, base, [], s_max=1.0) is None


def test_suavizado_no_mueve_los_puntos_de_control():
    dens = _dens_recta(41, 2.5)
    base = _base_lineal(dens, 1060.0, 1090.0)
    ctrl = [(25.0, 1075.0), (50.0, 1078.0)]
    zs = dv.perfil_desde_control(dens, base, ctrl, s_max=1.0)
    s = dv._estaciones(dens)
    for sc, zc in ctrl:
        i = min(range(len(s)), key=lambda k: abs(s[k] - sc))
        assert abs(zs[i] - zc) < 1e-6


def test_limpiar_vertices_pegados():
    pts = [(0.0, 0.0, 10.0), (0.05, 0.0, 10.5), (5.0, 0.0, 12.0),
           (5.1, 0.0, 12.1), (10.0, 0.0, 14.0)]
    out = dv._limpiar_vertices(pts, tol=0.3)
    assert len(out) == 3 and out[0] == pts[0] and out[-1] == pts[-1]


# --------------------------------------------------------------- recorte
class _CorredorFalso:
    """Corredor circular de radio r centrado en (0,0): basta para comprobar la
    logica de recorte sin necesitar QGIS."""

    def __init__(self, r):
        self.r = r

    def dentro(self, x, y):
        return math.hypot(x, y) < self.r


def _recortar(pts, r, long_min=0.0):
    return dv.recortar_contra_corredor(pts, _CorredorFalso(r), long_min)


def test_recorte_quita_solo_lo_que_esta_dentro():
    pts = [(0.0, 0.0, 10.0), (5.0, 0.0, 12.0), (10.0, 0.0, 14.0),
           (20.0, 0.0, 18.0)]
    piezas, quitado = _recortar(pts, 7.0)
    assert len(piezas) == 1
    p = piezas[0]
    assert abs(p[0][0] - 7.0) < 0.05         # empieza justo en el borde
    assert p[-1] == pts[-1]                  # el otro extremo intacto
    assert abs(quitado - 7.0) < 0.1


def test_recorte_no_toca_una_linea_que_ya_esta_fuera():
    pts = [(20.0, 0.0, 10.0), (30.0, 0.0, 12.0)]
    piezas, quitado = _recortar(pts, 7.0)
    assert piezas == [pts] and quitado < 1e-6


def test_recorte_de_los_dos_extremos():
    pts = [(0.0, 0.0, 10.0), (20.0, 0.0, 12.0), (0.5, 0.5, 10.0)]
    piezas, _ = _recortar(pts, 5.0)
    assert len(piezas) == 1
    p = piezas[0]
    assert math.hypot(p[0][0], p[0][1]) >= 4.9
    assert math.hypot(p[-1][0], p[-1][1]) >= 4.9


def test_linea_entera_dentro_desaparece():
    pts = [(0.0, 0.0, 10.0), (1.0, 0.0, 10.0), (2.0, 0.0, 10.0)]
    piezas, _ = _recortar(pts, 9.0)
    assert piezas == []


def test_entra_y_sale_por_el_MEDIO_y_la_linea_se_parte():
    """El caso que fallaba en el proyecto real: la divisoria se metia en el
    corredor por el medio y volvia a salir, asi que morder desde los extremos
    no quitaba nada. Tiene que partirse en dos."""
    pts = [(-30.0, 0.0, 20.0), (-20.0, 0.0, 18.0), (0.0, 2.0, 12.0),
           (20.0, 0.0, 18.0), (30.0, 0.0, 20.0)]
    piezas, quitado = _recortar(pts, 8.0)
    assert len(piezas) == 2, [len(p) for p in piezas]
    assert all(math.hypot(p[0][0], p[0][1]) >= 7.9 for p in piezas)
    assert all(math.hypot(p[-1][0], p[-1][1]) >= 7.9 for p in piezas)
    assert quitado > 15.0


def test_roza_el_corredor_sin_ningun_vertice_dentro():
    """Dos vertices fuera pero el segmento entre ellos pasa por el centro: sin
    sondear a lo largo del segmento no se detectaria."""
    pts = [(-40.0, 0.0, 20.0), (40.0, 0.0, 20.0)]
    piezas, quitado = _recortar(pts, 10.0)
    assert len(piezas) == 2 and quitado > 19.0


def test_los_munones_cortos_se_descartan():
    """Un trozo de cuatro metros junto a la confluencia no es una divisoria."""
    pts = [(-40.0, 0.0, 20.0), (-11.0, 0.0, 15.0), (11.0, 0.0, 15.0),
           (14.0, 0.0, 16.0)]
    piezas, _ = _recortar(pts, 10.0, long_min=8.0)
    assert len(piezas) == 1          # sobrevive solo el trozo largo
    assert _recortar(pts, 10.0, long_min=0.0)[0].__len__() == 2


def test_la_z_se_interpola_en_el_corte():
    pts = [(0.0, 0.0, 100.0), (20.0, 0.0, 120.0)]
    piezas, _ = _recortar(pts, 10.0)
    z0 = piezas[0][0][2]
    assert abs(z0 - 110.0) < 0.5, z0


# --------------------------------------------------------------- auxiliares
def test_monotonizar_respeta_el_sentido():
    assert dv._monotonizar([1.0, 3.0, 2.0, 5.0]) == [1.0, 3.0, 3.0, 5.0]
    assert dv._monotonizar([5.0, 3.0, 4.0, 1.0]) == [5.0, 3.0, 3.0, 1.0]


def test_monotonizar_no_aplasta_una_loma_LEGITIMA():
    """B-036. Una divisoria puede subir desde una confluencia, coronar y bajar a
    otra. Con el sentido decidido por los dos extremos, el punto de control de
    la corona —que es intocable— se convertia en un trinquete: todo lo que venia
    detras se aplanaba contra el hasta que el extremo anclado obligaba a soltar
    el desnivel de golpe."""
    zs = [10.0, 12.0, 20.0, 18.0, 16.0, 14.0, 5.0]
    out = dv._monotonizar(zs, fijos={2})       # la corona es punto de control
    assert out[2] == 20.0                      # el control no se mueve
    assert out == sorted(out[:3]) + sorted(out[2:], reverse=True)[1:]
    # y sobre todo: NADA de mesetas detras de la corona
    assert len({round(z, 6) for z in out[3:]}) == len(out[3:])


def test_monotonizar_no_deja_que_el_perfil_se_salga_entre_dos_fijos():
    """Entre dos puntos fijos el perfil no puede salirse del intervalo que ellos
    marcan: ahi es donde estaban los dientes."""
    out = dv._monotonizar([0.0, 50.0, -50.0, 10.0], fijos=set())
    assert min(out) >= 0.0 and max(out) <= 10.0


def test_extremo_alto_manda_la_distancia_al_cauce_no_la_cota():
    """P-19. Donde el cauce va sobre RELLENO, la ladera baja de el y su extremo
    mas alto es el PIE. Decidirlo por cota elige el extremo equivocado, y en
    cuanto se mueven las cotas de las divisorias el sintoma es inexplicable."""
    # pie pegado al cauce (x=0) y a cota ALTA; cabecera lejos y mas BAJA
    pts = [(0.0, 0.0, 1100.0), (30.0, 0.0, 1095.0), (60.0, 0.0, 1090.0)]
    dist = lambda x, _y: abs(x)                       # noqa: E731
    assert dv.extremo_alto(pts, dist) == len(pts) - 1, "la cabecera es la lejana"
    # sin invocable, respaldo por cota: elige el otro, y por eso hace falta el
    # criterio geometrico
    assert dv.extremo_alto(pts) == 0


def test_extremo_alto_con_la_linea_al_reves():
    pts = [(60.0, 0.0, 1090.0), (30.0, 0.0, 1095.0), (0.0, 0.0, 1100.0)]
    dist = lambda x, _y: abs(x)                       # noqa: E731
    assert dv.extremo_alto(pts, dist) == 0
    assert dv.extremo_alto([(0.0, 0.0, 1.0)], dist) == 0      # linea degenerada


def test_remuestrear_respeta_la_traza_y_los_extremos():
    """'m_fMaxDistOnRidges' del original (6.1 m en el Ej_2). Los puntos se toman
    SOBRE la polilinea, asi que la traza no se desplaza."""
    pts = [(0.7 * i, 0.0, 100.0 + 0.7 * i) for i in range(30)]   # 20.3 m a 0.7
    out = dv.remuestrear(pts, 6.1)
    assert out[0] == pts[0] and out[-1] == pts[-1]
    s = dv._estaciones([(p[0], p[1]) for p in out])
    paso = [s[i + 1] - s[i] for i in range(len(s) - 1)]
    assert max(paso) <= 6.1 + 1e-6, paso
    assert all(abs(p[1]) < 1e-9 for p in out)          # sigue sobre la recta
    for x, _y, z in out:                               # y la cota se interpola
        assert abs(z - (100.0 + x)) < 1e-6


def test_remuestrear_conserva_una_curva_cerrada():
    """El ajuste es una distancia MAXIMA entre vertices, no licencia para
    comerse la forma. En el Ej_2 el remuestreo ciego recortaba 1.8 m de una
    curva cerrada."""
    # horquilla: sube 10 m, gira 180 grados y baja
    pts = ([(0.0, y, 100.0) for y in range(0, 11)]
           + [(4.0, y, 100.0) for y in range(10, -1, -1)])
    out = dv.remuestrear(pts, 6.1)
    for p in pts:
        d = min(dv._dist_a_segmento(p, out[i], out[i + 1])
                for i in range(len(out) - 1))
        assert d <= dv.TOL_TRAZA_CRESTA + 1e-9, "se recorta %.2f m" % d


def test_remuestrear_no_toca_una_linea_ya_corta():
    pts = [(0.0, 0.0, 10.0), (2.0, 0.0, 11.0), (4.0, 0.0, 12.0)]
    assert dv.remuestrear(pts, 6.1) == pts
    assert dv.remuestrear(pts, 0.0) == pts


def test_limitar_pendiente():
    s = [0.0, 10.0, 20.0]
    zs = dv._limitar_pendiente([0.0, 10.0, 11.0], s, 0.5)
    assert abs(zs[1] - 5.0) < 1e-9


# ------------------------------------------------- ajuste de un extremo
def test_ajustar_el_pie_no_aplasta_la_ladera():
    """Una ladera va de cota baja (pie) a cota alta (cabecera). Al pegar el pie
    a la coronacion de la orilla, el resto tiene que seguir subiendo: la
    monotonia se aplica en el sentido REAL de la linea."""
    pts = [(0.0, 0.0, 1060.0), (10.0, 0.0, 1063.0), (20.0, 0.0, 1066.0),
           (30.0, 0.0, 1069.0), (40.0, 0.0, 1072.0)]
    out = dv.ajustar_extremo(pts, 1060.5, en_inicio=True, mezcla=15.0)
    assert abs(out[0][2] - 1060.5) < 1e-9
    assert abs(out[-1][2] - 1072.0) < 1e-9      # la cabecera no se toca
    zs = [p[2] for p in out]
    assert zs == sorted(zs), zs                 # sigue subiendo


def test_ajustar_la_cabecera_reparte_y_deja_monotona():
    pts = [(0.0, 0.0, 1060.0), (10.0, 0.0, 1070.8), (20.0, 0.0, 1070.8),
           (30.0, 0.0, 1068.3)]
    out = dv.ajustar_extremo(pts, 1071.5, en_inicio=False, mezcla=25.0)
    assert abs(out[-1][2] - 1071.5) < 1e-9
    zs = [p[2] for p in out]
    assert zs == sorted(zs), zs                 # ya no baja antes de morir


def test_ajustar_una_linea_descendente():
    """Una divisoria que baja del limite a la confluencia: mismo criterio."""
    pts = [(0.0, 0.0, 1100.0), (10.0, 0.0, 1090.0), (20.0, 0.0, 1080.0)]
    out = dv.ajustar_extremo(pts, 1075.0, en_inicio=False, mezcla=25.0)
    zs = [p[2] for p in out]
    assert zs == sorted(zs, reverse=True) and abs(zs[-1] - 1075.0) < 1e-9


def _meseta_mas_larga(zs, tol=0.01):
    peor = run = 1
    for i in range(1, len(zs)):
        run = run + 1 if abs(zs[i] - zs[i - 1]) <= tol else 1
        peor = max(peor, run)
    return peor


def test_bajar_mucho_la_cabecera_no_deja_una_meseta():
    """Si la correccion se reparte solo sobre `mezcla`, los vertices de mas
    alla conservan su cota vieja y el recorte de monotonia los arrastra a todos
    a la misma: sale una MESETA seguida de una rampa.

    Medido en el Ej_2 (Rom_Pla): la subcresta fid 65 subia 284.8 -> 303.2 m en
    siete vertices y despues se quedaba 48 m completamente planos a 303.2. Diez
    de sus 218 lineas tenian esa firma, con mesetas de hasta 27 vertices; el
    original no pasa de 2. La mezcla se ALARGA hasta donde la linea original ya
    rebasaba la cota objetivo."""
    # ladera de 100 m que sube de 284.8 a 310.0, cabecera forzada a 303.2
    pts = [(float(i) * 4.0, 0.0, 284.8 + i * (310.0 - 284.8) / 25.0)
           for i in range(26)]
    out = dv.ajustar_extremo(pts, 303.2, en_inicio=False, mezcla=25.0)
    zs = [p[2] for p in out]
    assert abs(zs[-1] - 303.2) < 1e-9
    assert zs == sorted(zs), zs                     # sigue subiendo
    assert abs(zs[0] - 284.8) < 1e-9                # el pie no se mueve
    assert _meseta_mas_larga(zs) <= 3, zs


def test_bajar_el_pie_tampoco_deja_meseta():
    """El mismo caso por el otro extremo: linea que desciende hacia el pie."""
    pts = [(float(i) * 4.0, 0.0, 310.0 - i * (310.0 - 284.8) / 25.0)
           for i in range(26)]
    out = dv.ajustar_extremo(pts, 303.2, en_inicio=True, mezcla=25.0)
    zs = [p[2] for p in out]
    assert abs(zs[0] - 303.2) < 1e-9
    assert zs == sorted(zs, reverse=True), zs
    assert _meseta_mas_larga(zs) <= 3, zs


def test_subir_la_cabecera_no_alarga_la_mezcla_sin_motivo():
    """Subir la cabecera de una linea que ya sube no rompe la monotonia, asi
    que la mezcla se queda como estaba y el resto de la linea no se toca."""
    pts = [(float(i) * 4.0, 0.0, 284.8 + i * 1.0) for i in range(26)]
    out = dv.ajustar_extremo(pts, 315.0, en_inicio=False, mezcla=20.0)
    zs = [p[2] for p in out]
    assert abs(zs[-1] - 315.0) < 1e-9
    assert zs == sorted(zs)
    # a mas de 20 m de la cabecera nada se ha movido
    assert abs(zs[0] - 284.8) < 1e-9 and abs(zs[10] - pts[10][2]) < 1e-9


# ------------------------------- perfil de ladera con la ECUACION
def _perfil_trapezoidal(x, D, dz, lc, lf=None):
    """Copia de ridges.perfil_trapezoidal para no arrastrar QGIS."""
    if lf is None:
        lf = min(lc, 0.30 * D)
    lc = max(0.5, min(lc, 0.6 * D))
    lf = max(0.5, min(lf, 0.9 * D - lc))
    s_m = dz / (D - lc / 2.0 - lf / 2.0)
    x = max(0.0, min(x, D))
    if x <= lc:
        return s_m * x * x / (2.0 * lc)
    if x <= D - lf:
        return s_m * (lc / 2.0 + (x - lc))
    y = x - (D - lf)
    return s_m * (lc / 2.0 + (D - lf - lc) + y - y * y / (2.0 * lf))


class _RidgesFalso(types.ModuleType):
    perfil_trapezoidal = staticmethod(_perfil_trapezoidal)


sys.modules.setdefault("ridges_falso", _RidgesFalso("ridges_falso"))


def _perfil_base(pts, z_alto, z_bajo, lc, desde_inicio=False):
    """perfil_base de divides.py, con la ecuacion inyectada."""
    s = dv._estaciones(pts)
    L = s[-1]
    dz = z_alto - z_bajo
    zs = []
    for si in s:
        x = si if desde_inicio else (L - si)
        zs.append(z_alto - _perfil_trapezoidal(x, L, dz, lc))
    zs[0 if desde_inicio else -1] = z_alto
    zs[-1 if desde_inicio else 0] = z_bajo
    return zs


def test_el_perfil_de_ladera_es_convexo_arriba_y_concavo_abajo():
    """La forma de Horton que describe el libro: cabeza convexa de longitud xc
    desde la cresta, tramo recto, pie concavo. La pendiente maxima esta en la
    union del convexo con el recto, no en los extremos."""
    pts = [(float(i) * 5.0, 0.0, 0.0) for i in range(21)]      # 100 m
    zs = _perfil_base(pts, 1100.0, 1060.0, lc=25.0, desde_inicio=True)
    s = dv._estaciones(pts)
    pend = [(zs[i] - zs[i + 1]) / (s[i + 1] - s[i]) for i in range(len(zs) - 1)]
    assert abs(zs[0] - 1100.0) < 1e-9 and abs(zs[-1] - 1060.0) < 1e-9
    assert zs == sorted(zs, reverse=True)          # baja siempre
    assert pend[0] < pend[len(pend) // 2]          # arranca tendido (convexo)
    assert pend[-1] < max(pend)                    # y acaba tendido (concavo)
    i_max = pend.index(max(pend))
    assert 3 <= i_max <= len(pend) - 3             # la maxima, en el interior


def test_la_ecuacion_respeta_las_dos_cotas_extremas():
    pts = [(float(i) * 4.0, 0.0, 0.0) for i in range(16)]
    zs = _perfil_base(pts, 1080.0, 1062.0, lc=20.0, desde_inicio=False)
    assert abs(zs[-1] - 1080.0) < 1e-9 and abs(zs[0] - 1062.0) < 1e-9
    assert zs == sorted(zs)


def test_la_ecuacion_no_deja_colas_verticales():
    """Una ladera plana con un salto de ocho metros al final: al rehacerla con
    la ecuacion el desnivel se reparte por toda la linea."""
    pts = [(float(i) * 4.0, 0.0, 1062.3) for i in range(16)]
    pts.append((62.6, 0.0, 1070.9))
    zs = _perfil_base(pts, 1070.9, 1062.3, lc=20.0, desde_inicio=False)
    s = dv._estaciones(pts)
    peor = max(abs(zs[i + 1] - zs[i]) / (s[i + 1] - s[i])
               for i in range(len(zs) - 1))
    assert peor < 0.40, peor
    assert abs(zs[-1] - 1070.9) < 1e-9


def test_el_pie_de_la_ladera_se_elige_por_distancia_al_cauce():
    """El PIE de una ladera es el extremo que esta junto al cauce, no el mas
    alto.

    Al oeste del canal principal de este proyecto el cauce va sobre relleno y
    la ladera BAJA de el hacia el perimetro: ahi el pie es el punto mas ALTO de
    la linea. Con el criterio de cota se agarraba el extremo equivocado y el
    empalme con el limite bajaba el arranque del cauce a la cota del terreno,
    dejando una meseta plana y una zanja en medio (medido: la ladera caia a
    1047.8 entre dos puntos a 1062.8 y 1062.0, cuando el motor la habia
    trazado bien de 1079.2 a 1062.0)."""
    # el motor traza de 1079.2 (junto al cauce) a 1062.0 (limite)
    pts = [(0.0, 0.0, 1079.2), (50.0, 0.0, 1070.0), (100.0, 0.0, 1062.0)]
    por_cota = 0 if pts[0][2] > pts[-1][2] else len(pts) - 1
    assert por_cota == 0, "el criterio de cota apunta al extremo del cauce"
    # el criterio correcto: el extremo LEJANO al cauce, que aqui es el ultimo
    d0, d1 = 1.0, 90.0            # distancias al eje de los dos extremos
    por_cauce = len(pts) - 1 if d0 <= d1 else 0
    assert por_cauce == len(pts) - 1
    assert por_cauce != por_cota, "los dos criterios difieren en este caso"


def test_la_monotonia_sigue_activa_por_defecto():
    """Donde SI debe ser monotona —una subcresta que sube del canal a la
    divisoria— el comportamiento no cambia."""
    pts = [(0.0, 0.0, 1060.0), (10.0, 0.0, 1070.8), (20.0, 0.0, 1070.8),
           (30.0, 0.0, 1068.3)]
    out = dv.ajustar_extremo(pts, 1071.5, en_inicio=False)
    zs = [p[2] for p in out]
    assert zs == sorted(zs)


def test_remuestrear_no_deja_micro_segmentos():
    """B-039. Los vertices que se conservan por forma se reinsertaban en su
    propia estacion, y esa estacion puede caer a centimetros de una marca
    regular. `remuestrear` es lo ULTIMO que toca la planta de una divisoria, asi
    que ese segmento diminuto llegaba tal cual al fichero: medido en el Ej_2, el
    4.3 % de los segmentos por debajo de 1 m —el mas corto de 0.43 m con un giro
    de 119 grados— cuando el original no tiene NI UNO."""
    # una recta con un racimo de quiebros espurios en medio
    pts = [(float(i) * 6.0, 0.0, 100.0) for i in range(20)]
    pts[9] = (54.0, 1.2, 100.0)
    pts.insert(10, (54.4, 1.4, 100.0))
    pts.insert(11, (54.9, 1.1, 100.0))
    out = dv.remuestrear(pts, 6.1)
    seg = [math.dist(out[i][:2], out[i + 1][:2]) for i in range(len(out) - 1)]
    assert min(seg) > 1.0, "segmento de %.2f m" % min(seg)


def test_remuestrear_se_queda_con_el_vertice_que_LLEVA_la_forma():
    """De cada racimo se conserva el que MAS se desvia, no el primero: quedarse
    con el primero se comia el apice de las curvas cerradas."""
    pts = [(float(i) * 6.0, 0.0, 100.0) for i in range(12)]
    # racimo con el apice en el del medio
    pts.insert(6, (36.0, 0.6, 100.0))
    pts.insert(7, (36.5, 3.0, 100.0))      # <- el apice
    pts.insert(8, (37.0, 0.6, 100.0))
    out = dv.remuestrear(pts, 6.1)
    assert any(abs(q[1] - 3.0) < 1e-9 for q in out), \
        "se ha perdido el apice: %s" % [round(q[1], 2) for q in out]
