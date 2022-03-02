import math
import pandas as pd
import time
from random import random

__author__ = 'Juan Pablo Donalisio'


class Simulador:
    def __init__(self, **kwargs):
        self.mostrar_desde = kwargs['mostrar_desde']
        self.mostrar_hasta = kwargs['mostrar_hasta']
        self.cant_simular = kwargs['cant_simular']

        self.tiempo_ingreso_informes = (kwargs['tiempo_ingreso_informes_desde'], kwargs[
            'tiempo_ingreso_informes_hasta'])  # Cada x minutos, viene una persona a informes
        self.tiempo_ingreso_reservas = (kwargs['tiempo_ingreso_reservas_desde'], kwargs[
            'tiempo_ingreso_reservas_hasta'])  # Cada x minutos, viene una persona a reservas

        # Cuando vino una persona que quiere ir a informes, demora x segundos en llegar a la mesa
        # Dividimos por sesenta porque este tiempo está en segundos.
        self.demora_llegar_informes = (
            kwargs['demora_llegar_informes_desde'] / 60, kwargs['demora_llegar_informes_hasta'] / 60)
        # Se demoran x segundos en llegar a la mesa de reservas desde la mesa de informes
        # di: Desde informes
        self.demora_llegar_reservas_di = (
            kwargs['demora_llegar_reservas_di_desde'] / 60, kwargs['demora_llegar_reservas_di_hasta'] / 60)
        # Se demoran x segundos en llegar a la mesa de reservas para alguien que acaba de llegar
        # rc: recien llegado
        self.demora_llegar_reservas_rc = (
            kwargs['demora_llegar_reservas_rc_desde'] / 60, kwargs['demora_llegar_reservas_rc_hasta'] / 60)

        self.tiempo_atencion_informes = (kwargs['tiempo_atencion_informes_desde'], kwargs[
            'tiempo_atencion_informes_hasta'])  # El tiempo de atencion en informes es de x minutos
        self.tiempo_atencion_reservas = (kwargs['tiempo_atencion_reservas_desde'], kwargs[
            'tiempo_atencion_reservas_hasta'])  # El tiempo de atencion en la mesa de reservas es de x minutos

        self.probabilidad_irse = kwargs['probabilidad_irse']  # Probabilidad de retirarse luego de ser atendido

        self.demora_salir = (kwargs['demora_salir_desde'] / 60,
                             kwargs['demora_salir_hasta'] / 60)  # Segundos que demora una persona en salir

    def simular(self):
        camino_salida = CaminoSalida(self.demora_salir)
        mesa_reservas = MesaReservas(self.tiempo_atencion_reservas, self.demora_llegar_reservas_di,
                                     self.demora_llegar_reservas_rc, camino_salida)
        mesa_informes = MesaInformes(self.tiempo_atencion_informes, self.demora_llegar_informes, self.probabilidad_irse,
                                     camino_salida, mesa_reservas)
        generador_personas = GeneradorPersonas(self.tiempo_ingreso_informes, self.tiempo_ingreso_reservas,
                                               mesa_informes, mesa_reservas)

        reloj = 0
        evento = 'Inicializacion'
        fila = 0
        data = [[fila, format_time(reloj), evento] +
                generador_personas.getEstadoActual() +
                mesa_informes.getEstadoActual() +
                mesa_reservas.getEstadoActual() +
                camino_salida.getEstadoActual() + [0]]

        while Persona.cant <= self.cant_simular:
            fila += 1
            prox_evento, descartados = self.getProxEvento(generador_personas, mesa_informes, mesa_reservas,
                                                          camino_salida)
            for evento_descartado in descartados:
                evento_descartado.limpiar()
            reloj, evento = prox_evento.procesarProxEvento()

            if fila == 1 or (self.mostrar_desde <= fila <= self.mostrar_hasta) or Persona.cant == self.cant_simular:
                data_to_add = [fila, format_time(reloj), evento]
                for manager in [generador_personas, mesa_informes, mesa_reservas, camino_salida]:
                    data_to_add += manager.getEstadoActual()
                data_to_add += [Persona.cant]
                data.append(data_to_add)

            if Persona.cant == self.cant_simular:
                break

        titles = ['fila', 'reloj', 'evento',
                  'RND', 'tiempo_llegada [Informes]', 'prox_llegada [Informes]',
                  'RND', 'tiempo_llegada [Reservas]', 'prox_llegada [Reservas]',
                  'en_transito [Informes]', 'cola [Informes]', 'estado [Informes]',
                  'RND', 'tiempo_atencion [Informes]', 'fin_atencion [Informes]', 'RND_salida', 'sale_sistema',
                  'en_transito [Reservas]', 'cola [Reservas]', 'estado [Reservas]',
                  'RND', 'tiempo_atencion [Reservas]', 'fin_atencion [Reservas]',
                  'en_transito [Salida]',
                  'personas_simuladas']

        Persona.cant = 0
        return pd.DataFrame(data=data, columns=titles).to_json(orient='split')

    def getProxEvento(self, generador_personas, mesa_informes, mesa_reservas, camino_salida):
        eventos_posibles = {generador_personas: generador_personas.getProxEvento(),
                            mesa_informes: mesa_informes.getProxEvento(),
                            mesa_reservas: mesa_reservas.getProxEvento(),
                            camino_salida: camino_salida.getProxEvento()}
        proximo_evento = min(eventos_posibles, key=eventos_posibles.get)

        descartados = []
        for evento in eventos_posibles:
            if evento != proximo_evento:
                descartados.append(evento)

        return proximo_evento, descartados


class Persona:
    cant = 0

    def __init__(self, tipo):
        Persona.cant += 1

        self.fin = None
        self.rnd = None
        self.demora = None

        # 0: Persona que viene directo a informes
        # 1: Persona que viene directo a reservas
        self.tipo = tipo

    def setTiempos(self, rnd, demora, llegada):
        self.rnd = rnd
        self.demora = demora
        self.fin = llegada

    def json(self):
        return {'tipo': 'Persona que vino a informes' if self.tipo == 0 else 'Persona que vino directo a reservas',
                'rnd': digitos(self.rnd), 'demora': format_time(self.demora), 'fin': format_time(self.fin)}

    def __gt__(self, other):
        return self.fin > other.fin


class GeneradorPersonas:
    def __init__(self,
                 tiempos_informes, tiempos_reservas, mesa_informes, mesa_reservas):
        self.mesa_reservas: MesaReservas = mesa_reservas
        self.mesa_informes: MesaInformes = mesa_informes
        self.tiempo_desde_llegada_informes = tiempos_informes[0]
        self.tiempo_hasta_llegada_informes = tiempos_informes[1]
        self.tiempo_hasta_llegada_reservas = tiempos_reservas[0]
        self.tiempo_desde_llegada_reservas = tiempos_reservas[1]

        # __init__ es la inicializacion -> Cuando se crea el generador de personas, por ende tenemos que
        # calcular los randoms para informes y reservas, junto con sus tiempos de llegada y sus proximas llegadas
        self.rnd_llegada_informe = random()
        self.tiempo_llegada_informe = self.rnd_llegada_informe * (
                self.tiempo_hasta_llegada_informes - self.tiempo_desde_llegada_informes) + self.tiempo_desde_llegada_informes
        # Como estamos inicializando el generador, se supone que el reloj esta en cero, por ende la proxima llegada
        # es igual al tiempo de llegada
        self.prox_llegada_informe = self.tiempo_llegada_informe

        self.rnd_llegada_reserva = random()
        self.tiempo_llegada_reserva = self.rnd_llegada_reserva * (
                self.tiempo_hasta_llegada_reservas - self.tiempo_desde_llegada_reservas) + self.tiempo_desde_llegada_reservas
        self.prox_llegada_reserva = self.tiempo_llegada_reserva

    def getProxEvento(self):
        return min(self.prox_llegada_informe, self.prox_llegada_reserva)

    def getEstadoActual(self):
        return [
            digitos(self.rnd_llegada_informe), format_time(self.tiempo_llegada_informe),
            format_time(self.prox_llegada_informe),
            digitos(self.rnd_llegada_reserva), format_time(self.tiempo_llegada_reserva),
            format_time(self.prox_llegada_reserva)
        ]

    def procesarProxEvento(self):
        if self.prox_llegada_informe < self.prox_llegada_reserva:
            reloj = self.prox_llegada_informe

            self.rnd_llegada_informe = random()
            self.tiempo_llegada_informe = self.rnd_llegada_informe * (
                    self.tiempo_hasta_llegada_informes - self.tiempo_desde_llegada_informes) + self.tiempo_desde_llegada_informes
            self.prox_llegada_informe = reloj + self.tiempo_llegada_informe

            self.mesa_informes.addPersona(Persona(0), reloj)
            return reloj, 'llegada_persona [Informes]'
        reloj = self.prox_llegada_reserva

        self.rnd_llegada_reserva = random()
        self.tiempo_llegada_reserva = self.rnd_llegada_reserva * (
                self.tiempo_hasta_llegada_reservas - self.tiempo_desde_llegada_reservas) + self.tiempo_desde_llegada_reservas
        self.prox_llegada_reserva = reloj + self.tiempo_llegada_reserva

        self.mesa_reservas.addPersona(Persona(1), reloj)
        return reloj, 'llegada_persona [Reservas]'

    def limpiar(self):
        self.rnd_llegada_informe = self.tiempo_llegada_informe = self.rnd_llegada_reserva = self.tiempo_llegada_reserva = None


class CaminoSalida:
    def __init__(self, tiempo_salir):
        self.tiempo_salir = tiempo_salir
        self.personas_transitando = []

    def addPersona(self, persona, reloj):
        rnd = random()
        demora = rnd * (self.tiempo_salir[1] - self.tiempo_salir[0]) + self.tiempo_salir[0]
        persona.setTiempos(rnd, demora, reloj + demora)
        self.personas_transitando.append(persona)

    def getProxEvento(self):
        if len(self.personas_transitando) > 0:
            return min(self.personas_transitando).fin
        else:
            return math.inf

    def getEstadoActual(self):
        return [[persona.json() for persona in self.personas_transitando]]

    def procesarProxEvento(self):
        persona = min(self.personas_transitando)
        self.personas_transitando.remove(persona)
        return persona.fin, 'salida_sistema'

    def limpiar(self):
        pass


class Mesa:
    def __init__(self, tiempo_atencion, camino_salida: CaminoSalida):
        self.tipo_mesa = ''
        self.camino_salida = camino_salida
        self.tiempo_atencion = tiempo_atencion

        # La cola de transito serian todas las personas (Persona) que estan "en camino" hacia una mesa
        self.en_transito = []
        # La cola de 'yendose' serian todas las personas (Persona) que estan transitando hacia la salida del sistema
        self.yendose = []

        self.cola = []  # Personas que estan en la cola de la mesa
        self.atendiendo: Persona = None  # Persona que esta siendo atendida

    def getProxEvento(self):
        tiempos_transito = [persona.fin for persona in self.en_transito]
        proxima_salida_transito = min(tiempos_transito) if len(tiempos_transito) > 0 else math.inf
        fin_atencion = self.atendiendo.fin if self.atendiendo is not None else math.inf
        return min([proxima_salida_transito, fin_atencion])

    def addPersona(self, Persona, reloj):
        pass

    def getEstadoActual(self):
        en_transito = []
        for persona in self.en_transito:
            en_transito.append(persona.json())

        if self.atendiendo is not None:
            estado_persona_atendiendo = [digitos(self.atendiendo.rnd), format_time(self.atendiendo.demora),
                                         format_time(self.atendiendo.fin)]
        else:
            estado_persona_atendiendo = [None, None, None]

        return [en_transito, len(self.cola),
                'Ocupado' if self.atendiendo is not None else 'Libre',
                ] + estado_persona_atendiendo

    def procesarProxEvento(self):
        tiempos_transito = [persona.fin for persona in self.en_transito]
        proxima_salida_transito = min(tiempos_transito) if len(tiempos_transito) > 0 else math.inf
        fin_atencion = self.atendiendo.fin if self.atendiendo is not None else math.inf
        reloj = min([proxima_salida_transito, fin_atencion])

        # El proximo evento es una persona que termina de transitar
        if proxima_salida_transito == reloj:
            persona = min(self.en_transito)
            self.en_transito.remove(persona)
            self.mover_a_cola(persona, reloj)
            return reloj, f'fin_transito {self.tipo_mesa}'

        # El proximo evento es una persona termina de ser atendida
        elif fin_atencion == reloj:
            if len(self.cola) > 0:  # Hay gente en la cola
                persona_sale = self.atendiendo
                persona = self.cola.pop(0)
                rnd = random()
                demora = rnd * (self.tiempo_atencion[1] - self.tiempo_atencion[0]) + self.tiempo_atencion[0]
                persona.setTiempos(rnd, demora, reloj + demora)
                self.atendiendo = persona
            else:  # No hay nadie en la cola
                persona_sale = self.atendiendo
                self.atendiendo = None
            self.procesar_fin_atencion(persona_sale, reloj)

            return reloj, f'fin_atencion {self.tipo_mesa}'

    def mover_a_cola(self, persona: Persona, reloj):
        if self.atendiendo is None:
            rnd = random()
            demora = rnd * (self.tiempo_atencion[1] - self.tiempo_atencion[0]) + self.tiempo_atencion[0]
            persona.setTiempos(rnd, demora, reloj + demora)
            self.atendiendo = persona
        else:
            persona.setTiempos(None, None, None)
            self.cola.append(persona)

    def procesar_fin_atencion(self, persona, reloj):
        pass

    def limpiar(self):
        if self.atendiendo is not None:
            self.atendiendo.rnd = None
            self.atendiendo.demora = None


class MesaReservas(Mesa):
    def __init__(self, tiempo_atencion, demora_llegar_di, demora_llegar_rc, camino_salida: CaminoSalida):
        super().__init__(tiempo_atencion, camino_salida)
        self.tipo_mesa = 'Reservas'
        self.camino_salida = camino_salida
        self.demora_llegar_rc = demora_llegar_rc
        self.demora_llegar_di = demora_llegar_di

    def addPersona(self, persona, reloj):
        if persona.tipo == 0:
            # Viene desde informes, por ende hay que usar los tiempos para una persona que viene desde informes
            rnd = random()
            demora = rnd * (self.demora_llegar_di[1] - self.demora_llegar_di[0]) + self.demora_llegar_di[0]
            llegada = reloj + demora
        else:
            # Recien llega y viene directo a reservas, por ende hay que usar los tiempos para un recien llegado
            rnd = random()
            demora = rnd * (self.demora_llegar_rc[1] - self.demora_llegar_rc[0]) + self.demora_llegar_rc[0]
            llegada = reloj + demora

        persona.setTiempos(rnd, demora, llegada)
        self.en_transito.append(persona)

    def procesar_fin_atencion(self, persona, reloj):
        # Como es la mesa de reservas, al finalizar la atencion, una persona sale del sistema
        self.camino_salida.addPersona(persona, reloj)


class MesaInformes(Mesa):
    def __init__(self, tiempo_atencion, demora_llegar, probabilidad_salir_sistema,
                 camino_salida: CaminoSalida, mesaReservas: MesaReservas):
        super().__init__(tiempo_atencion, camino_salida)
        self.tipo_mesa = 'Informes'
        self.mesaReservas = mesaReservas
        self.probabilidad_salir_sistema = probabilidad_salir_sistema
        self.demora_llegar = demora_llegar

        self.rnd = None
        self.sale = False

    def addPersona(self, persona, reloj):
        rnd = random()
        demora = rnd * (self.demora_llegar[1] - self.demora_llegar[0]) + self.demora_llegar[0]
        llegada = reloj + demora
        persona.setTiempos(rnd, demora, llegada)
        self.en_transito.append(persona)

    def getEstadoActual(self):
        return super().getEstadoActual() + [digitos(self.rnd) if self.rnd else None, 'Si' if self.sale else 'No']

    def procesar_fin_atencion(self, persona, reloj):
        # Como es la mesa de informes, al finalizar la atencion, una persona puede o ir a la mesa de reservas, o salir
        # del sistema
        self.rnd = random()
        if self.rnd <= self.probabilidad_salir_sistema:
            self.sale = True
            self.camino_salida.addPersona(persona, reloj)
        else:
            self.sale = False
            self.mesaReservas.addPersona(persona, reloj)

    def limpiar(self):
        super().limpiar()
        self.rnd = None
        self.sale = None


def format_time(minutes):
    if minutes is None:
        return None
    if minutes >= 1:
        return time.strftime('%H:%M:%S', time.gmtime(minutes * 60))
    else:
        return f'{"{:.2f}".format(minutes * 60)} segs'


def digitos(numero):
    if numero:
        return "{:.4f}".format(numero)
    return numero


if __name__ == '__main__':
    example_json = {
        'tiempo_ingreso_informes_desde': 8,
        'tiempo_ingreso_informes_hasta': 12,

        'tiempo_ingreso_reservas_desde': 12,
        'tiempo_ingreso_reservas_hasta': 18,

        'demora_llegar_informes_desde': 3,
        'demora_llegar_informes_hasta': 7,

        'demora_llegar_reservas_di_desde': 5,
        'demora_llegar_reservas_di_hasta': 15,

        'demora_llegar_reservas_rc_desde': 12,
        'demora_llegar_reservas_rc_hasta': 18,

        'tiempo_atencion_informes_desde': 4,
        'tiempo_atencion_informes_hasta': 14,

        'tiempo_atencion_reservas_desde': 5,
        'tiempo_atencion_reservas_hasta': 9,

        'probabilidad_irse': .6,

        'demora_salir_desde': 15,
        'demora_salir_hasta': 25,

        'mostrar_desde': 10,
        'mostrar_hasta': 20,

        'cant_simular': 20
    }

    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    simulacion = Simulador(**example_json)
    print(simulacion.simular())
