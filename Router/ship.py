from .utils.debug import Debug
from .utils.misc import get_by_path
from .context import Context

class Ship:
    def __init__(self, entry:dict) -> None:
        """ Ship details. Used to store ship loadout and calculate attributes for route plotting. """
        self.id:str = str(entry.get('ShipID', '')).strip()
        self.type:str = entry.get('Ship', '').strip()
        self.ident:str = entry.get('ShipIdent', '').strip()
        self.name:str = entry.get('ShipName', '').strip() or self.ident or self.type or '?'

        self.fuel_power:float = 1.0
        self.fuel_multiplier:float = 1.0
        self.max_fuel_per_jump:float = 0.0
        self.base_mass:float = 0.0
        self.optimal_mass:float = 0.0
        self.tank_size:float = 0.0
        self.internal_tank_size:float = 0.0
        self.range_boost:int = 0
        self.range:float = 32.0
        self.supercharge_multiplier:int = 4
        self.injection_multiplier:int = 2

        # The journal loadout entry
        self.loadout:dict = {}

        # If we get an actual entry we can populate the loadout and calculate derived attributes.
        if entry.get('event', None) != 'Loadout':
            Debug.logger.error(f"Not an event {entry}, cannot initialize ship")
            if entry.get('loadout', None) == None:
                Debug.logger.debug(f"Event has no loadout, cannot initialize ship")
                return
            entry = entry['loadout']

        if Context.modules == []:
            Debug.logger.error(f"Modules not loaded, cannot initialize ship.")
            return

        self.loadout = entry

        # Create Standard Loadout Exchange Format (SLEF)
        self.slef:list = [{
                "header": { "appName": Context.plugin_title, "appVersion": Context.plugin_version.__str__()},
                "data": entry
            }]

        fsd:dict = [m for m in entry.get('Modules', []) if m['Slot'] == 'FrameShiftDrive'][0]
        fsd_type:str = fsd['Item']

        self.supercharge_multiplier = 6 if fsd_type.lower().endswith('overchargebooster_mkii') else 4

        tmp:list = [f for f in Context.modules if f['symbol'].lower() == fsd_type.lower()]
        if tmp == []:
            Debug.logger.error(f"FSD not found in Coriolis data: {fsd_type.lower()} {Context.modules}")
            return
        fsd_info:dict = tmp[0]

        self.fuel_power:float = fsd_info.get('fuelpower', 1.0) # fuelpower
        self.fuel_multiplier:float = fsd_info.get('fuelmul', 1.0) # fuelmul
        self.max_fuel_per_jump:float = fsd_info.get('maxfuel', 0.0) # maxfuel

        self.base_mass:float = round(entry.get('UnladenMass', 0) + get_by_path(entry, ['FuelCapacity', 'Reserve'], 0), 2)

        # Optimal mass, from engineering if mass manager present, else from FSD data
        # @TODO: What about deep charge?
        fsdmods:list = [m['Value'] for m in get_by_path(fsd, ['Engineering', 'Modifiers'], []) if m['Label'] == 'FSDOptimalMass']
        self.optimal_mass:float = round(fsdmods[0] if fsdmods != [] else fsd_info.get('optmass', 0.0), 2) # optmass

        # Main tank
        ft_type:str = [m['Item'] for m in entry.get('Modules', []) if m['Slot'] == 'FuelTank'][0]
        ft:dict = [f for f in Context.modules if f['symbol'].lower() == ft_type.lower()][0]
        self.tank_size:float = ft.get('fuel', 0)

        # Reserve tank
        self.internal_tank_size:float = get_by_path(entry, ['FuelCapacity', 'Reserve'], 0.0) # reserve tank size

        # Additional tanks
        fts:list = [m['Item'] for m in entry.get('Modules', []) if m['Slot'] != 'FuelTank' and m['Item'].startswith('int_fueltank')]
        for ft_type in fts:
            ft:dict = [f for f in Context.modules if f['symbol'].lower() == ft_type.lower()][0]
            self.tank_size += ft.get('fuel', 0)

        # Guardian FSD booster
        gfbs:list = [m['Item'] for m in entry.get('Modules', []) if m['Item'].startswith('int_guardianfsdbooster')]
        if gfbs != []:
            gfb:dict = [f for f in Context.modules if f['symbol'].lower() == gfbs[0].lower()][0]
            self.range_boost = gfb.get('jumpboost', 0.0) # range boost from guardian FSD booster

        # Base range calculation
        self.range:float = self.get_range()


    def get_range(self, cargo:int = 0) -> float:
        """ Return the range of this ship with a given quantity of cargo """
        try:
            return round((self.optimal_mass / (self.base_mass + self.tank_size + cargo)) * \
                                (self.max_fuel_per_jump / self.fuel_multiplier) ** \
                                (1 / self.fuel_power) + \
                                self.range_boost, 2)
        except Exception:
            return 32.0


    def __repr__(self) -> str:
        return f"ID {self.id}, name {self.name}, type {self.type}, unladen range {self.range:.2f}ly)"

    def __str__(self) -> str:
        return self.__repr__()

    def as_dict(self) -> dict:
        return self.loadout
