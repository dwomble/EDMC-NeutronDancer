from utils.Debug import Debug
from utils.misc import get_by_path
from .context import Context


SAVE_LIST:list = ['id', 'name', 'type', 'loadout', 'supercharge_mult', 'fuel_power', 'fuel_multiplier',
                      'max_fuel_per_jump', 'base_mass', 'optimal_mass',
                      'internal_tank_size', 'tank_size', 'reserve_size', 'range_boost', 'range']
class Ship:
    def __init__(self, entry:dict) -> None:
        """ Details of a ship along with calculations for jump range etc. """
        self.loadout:dict = {}

        # This is used when we're initlializing from saved route data

        Debug.logger.debug(f"Initializing: {entry}")
        #for key in SAVE_LIST:
        #    setattr(self, key, entry.get(key, None))

        if entry.get('event', None) != 'Loadout':
            Debug.logger.debug(f"Not an event")
            if entry.get('loadout', None) == None:
                Debug.logger.debug(f"Not a save")
                return
            entry = entry['loadout']

        self.loadout = entry

        self.slef:list = [
            {
                "header": {
                    "appName": "EDMC-NeutronDancer",
                    "appVersion": "2.0.0-dev"
                    },
                "data": entry
            }
        ]

        # This is used when we're initializing from a journal entry
        self.id:str = str(entry.get('ShipID', ''))
        self.name:str = entry.get('ShipName', '')
        self.type = entry.get('Ship', '')

        fsd:dict = [m for m in entry.get('Modules', []) if m['Slot'] == 'FrameShiftDrive'][0]
        fsd_type:str = fsd['Item']

        self.supercharge_mult:int = 6 if fsd_type.lower().endswith('overchargebooster_mkii') else 4

        if Context.modules == []:
            Debug.logger.debug(f"No modules!")
            return

        tmp:list = [f for f in Context.modules if f['symbol'].lower() == fsd_type.lower()]
        if tmp == []:
            Debug.logger.debug(f"FSD not found in Coriolis data: {fsd_type.lower()} {Context.modules}")
        fsd_deets:dict = tmp[0]

        self.fuel_power:float = fsd_deets.get('fuelpower', 1.0) # fuelpower
        self.fuel_multiplier:float = fsd_deets.get('fuelmul', 1.0) # fuelmul
        self.max_fuel_per_jump:float = fsd_deets.get('maxfuel', 0.0) # maxfuel

        self.base_mass:float = round(entry.get('UnladenMass', 0) + get_by_path(entry, ['FuelCapacity', 'Reserve'], 0), 2)

        # Optimal mass, from engineering if mass manager present, else from FSD data
        mods:list = [m['Value'] for m in get_by_path(fsd, ['Engineering', 'Modifiers'], []) if m['Label'] == 'FSDOptimalMass']
        #Debug.logger.debug(f"Mass: {mods} {fsd}")
        self.optimal_mass:float = round(mods[0] if mods != [] else fsd_deets.get('optmass', 0.0), 2) # optmass

        # Main tank
        ft_type:str = [m['Item'] for m in entry.get('Modules', []) if m['Slot'] == 'FuelTank'][0]
        ft:dict = [f for f in Context.modules if f['symbol'].lower() == ft_type.lower()][0]
        self.tank_size:float = ft.get('fuel', 0)
        # Additional tanks
        fts:list = [m['Item'] for m in entry.get('Modules', []) if m['Slot'] != 'FuelTank' and m['Item'].startswith('int_fueltank')]
        for ft_type in fts:
            ft:dict = [f for f in Context.modules if f['symbol'].lower() == ft_type.lower()][0]
            self.tank_size += ft.get('fuel', 0)

        # Reserve tank
        self.internal_tank_size:float = get_by_path(entry, ['FuelCapacity', 'Reserve'], 0.0) # reserve tank size

        # Guardian FSD booster
        self.range_boost:int = 0
        gfbs:list = [m['Item'] for m in entry.get('Modules', []) if m['Item'].startswith('int_guardianfsdbooster')]
        if gfbs != []:
            gfb:dict = [f for f in Context.modules if f['symbol'].lower() == gfbs[0].lower()][0]
            self.range_boost = gfb.get('jumpboost', 0.0) # range boost from guardian FSD booster

        Debug.logger.debug(f"Calculating range: {self.optimal_mass} {self.base_mass} {self.tank_size} {self.max_fuel_per_jump} {self.fuel_multiplier} {self.fuel_power}")
        Debug.logger.debug(f"{self.optimal_mass} / {(self.base_mass + self.internal_tank_size + self.tank_size)} * {(self.max_fuel_per_jump / self.fuel_multiplier)} ^ {(1 / self.fuel_power)}")
        # Final range calculation
        self.range:float = round((self.optimal_mass / (self.base_mass + self.tank_size)) * \
                            (self.max_fuel_per_jump / self.fuel_multiplier) ** \
                            (1 / self.fuel_power) + \
                            self.range_boost, 2)
        Debug.logger.debug(f"Range: {self.range}")

    def __repr__(self) -> str:
        return f"Ship(id={self.id}, name={self.name}, type={self.type}, range={self.range:.2f}ly)"

    def __str__(self) -> str:
        return self.__repr__()

    def to_dict(self) -> dict:
        return self.loadout
        return {key: getattr(self, key) for key in SAVE_LIST}
