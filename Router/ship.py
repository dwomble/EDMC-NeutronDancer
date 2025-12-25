from utils.Debug import Debug
from utils.misc import get_by_path
from .context import Context

""" Ship object containing details and calculations for jump range etc. """
class Ship:
    def __init__(self, entry:dict) -> None:
        """ Details of a ship along with calculations for jump range etc. """

        # This is used when we're initlializing from saved route data
        init:list = ['id', 'name', 'type', 'supercharge_mult',
                      'fuel_power', 'fuel_multiplier',
                      'max_fuel_per_jump', 'base_mass', 'optimal_mass',
                      'internal_tank_size', 'tank_size', 'reserve_size',
                      'range_boost', 'range']

        for key in init:
            setattr(self, key, entry.get(key, None))

        if entry.get('ShipID', None) is None:
            return

        # This is used when we're initializing from a journal entry
        self.id:str = str(entry.get('ShipID', ''))
        self.name:str = entry.get('ShipName', '')
        self.type = entry.get('Ship', '')

        fsd:dict = [m for m in entry.get('Modules', []) if m['Slot'] == 'FrameShiftDrive'][0]
        fsd_type:str = fsd['Item']

        self.supercharge_mult:int = 6 if fsd_type.lower().endswith('overchargebooster_mkii') else 4

        if Context.router.modules == []:
            Debug.logger.debug(f"No modules!")
            return

        tmp:list = [f for f in Context.router.modules if f['symbol'].lower() == fsd_type.lower()]
        if tmp == []:
            Debug.logger.debug(f"FSD not found in Coriolis data: {fsd_type.lower()} {Context.router.modules}")
        fsd_deets:dict = tmp[0]

        self.fuel_power:float = fsd_deets.get('fuelpower', 1.0) # fuelpower
        self.fuel_multiplier:float = fsd_deets.get('fuelmul', 1.0) # fuelmul
        self.max_fuel_per_jump:float = fsd_deets.get('maxfuel', 0.0) # maxfuel

        self.base_mass:float = round(entry.get('UnladenMass', 0), 2) # ? maybe right?

        # Optimal mass, from engineering if mass manager present, else from FSD data
        mods:list = [m['Value'] for m in get_by_path(fsd, ['Engineering', 'Modifiers'], []) if m['Label'] == 'FSDOptimalMass']
        Debug.logger.debug(f"Mass: {mods} {fsd}")
        self.optimal_mass:float = round(mods[0] if mods != [] else fsd_deets.get('optmass', 0.0), 2) # optmass

        # Main tank
        ft_type:str = [m['Item'] for m in entry.get('Modules', []) if m['Slot'] == 'FuelTank'][0]
        ft:dict = [f for f in Context.router.modules if f['symbol'].lower() == ft_type.lower()][0]
        self.internal_tank_size:float = ft.get('fuel', 0)

        # Additional tanks
        self.tank_size:float = 0.0 # Maybe this should include the main tank?
        fts:list = [m['Item'] for m in entry.get('Modules', []) if m['Slot'] != 'FuelTank' and m['Item'].startswith('int_fueltank')]
        for ft_type in fts:
            ft:dict = [f for f in Context.router.modules if f['symbol'].lower() == ft_type.lower()][0]
            self.tank_size += ft.get('fuel', 0)

        # Reserve tank
        self.reserve_size:float = get_by_path(entry, ['FuelCapacity', 'Reserve'], 0.0) # reserve tank size

        # Guardian FSD booster
        self.range_boost:int = 0
        gfbs:list = [m['Item'] for m in entry.get('Modules', []) if m['Item'].startswith('int_guardianfsdbooster')]
        if gfbs != []:
            gfb:dict = [f for f in Context.router.modules if f['symbol'].lower() == gfbs[0].lower()][0]
            self.range_boost = gfb.get('jumpboost', 0.0) # range boost from guardian FSD booster

        Debug.logger.debug(f"Calculating range: {self.optimal_mass} {self.base_mass} {self.internal_tank_size} {self.tank_size} {self.max_fuel_per_jump} {self.fuel_multiplier} {self.fuel_power}")
        Debug.logger.debug(f"{self.optimal_mass} / {(self.base_mass + self.internal_tank_size + self.tank_size)} * {(self.max_fuel_per_jump / self.fuel_multiplier)} ^ {(1 / self.fuel_power)}")
        # Final range calculation
        self.range:float = round((self.optimal_mass /  (self.base_mass + self.internal_tank_size + self.tank_size)) * \
                            (self.max_fuel_per_jump / self.fuel_multiplier) ** \
                            (1 / self.fuel_power) + \
                            self.range_boost, 2)
        Debug.logger.debug(f"Range: {self.range}")

    def __repr__(self) -> str:
        return f"Ship(id={self.id}, name={self.name}, type={self.type}, range={self.range:.2f}ly)"

    def __str__(self) -> str:
        return self.__repr__()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "range": self.range,
            "supercharge_mult": self.supercharge_mult,
            "fuel_power": self.fuel_power,
            "fuel_multiplier": self.fuel_multiplier,
            "max_fuel_per_jump": self.max_fuel_per_jump,
            "base_mass": self.base_mass,
            "optimal_mass": self.optimal_mass,
            "internal_tank_size": self.internal_tank_size,
            "tank_size": self.tank_size,
            "reserve_size": self.reserve_size,
            "range_boost": self.range_boost,
            "range": self.range
        }
