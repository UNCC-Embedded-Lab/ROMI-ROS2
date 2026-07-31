# Direct I2C interface to the onboard LSM6DS33 accelerometer/gyro.
#
# The Romi 32U4 Control Board's AVR firmware (RomiRPiSlaveDemo.ino) does
# NOT relay IMU data through its I2C slave buffer: PololuRPiSlave's TWI
# slave interrupt and the standard Wire library's TWI master interrupt
# both need the AVR's single ISR(TWI_vect) vector, so they can't be
# linked into the same sketch. See the comment at the top of that
# sketch for details.
#
# Instead, since the LSM6DS33 sits on the same physical I2C bus that
# the Raspberry Pi already uses to reach the AVR slave (address 20),
# the Pi can talk to the LSM6DS33 directly at its own address.
import smbus
import struct

# LSM6DS33 I2C address depends on the state of its SA0 pin.
_CANDIDATE_ADDRESSES = (0x6B, 0x6A)

_WHO_AM_I = 0x0F
_WHO_AM_I_EXPECTED = 0x69

_CTRL1_XL = 0x10
_CTRL2_G = 0x11
_CTRL3_C = 0x12

# Gyro (X/Y/Z) and accel (X/Y/Z) output registers are contiguous, so a
# single 12-byte block read starting at OUTX_L_G returns all six axes
# once IF_INC (auto-increment) is enabled via CTRL3_C.
_OUTX_L_G = 0x22


class Lsm6Interface:
    def __init__(self, bus_number=1):
        self.bus = smbus.SMBus(bus_number)
        self.address = None

    def init(self):
        """Probe both possible addresses and confirm the WHO_AM_I ID."""
        for addr in _CANDIDATE_ADDRESSES:
            try:
                who_am_i = self.bus.read_byte_data(addr, _WHO_AM_I)
            except OSError:
                continue
            if who_am_i == _WHO_AM_I_EXPECTED:
                self.address = addr
                return True
        return False

    def enable_default(self):
        if self.address is None:
            raise RuntimeError("LSM6DS33 not initialized; call init() first")

        # Accelerometer: ODR = 52 Hz (normal mode), FS_XL = +/-2 g
        self.bus.write_byte_data(self.address, _CTRL1_XL, 0x30)
        # Gyro: ODR = 208 Hz (normal mode), FS_G = +/-245 dps
        self.bus.write_byte_data(self.address, _CTRL2_G, 0x50)
        # IF_INC = 1 (auto-increment register address on multi-byte reads)
        self.bus.write_byte_data(self.address, _CTRL3_C, 0x04)

    def read(self):
        """Return raw (accelX, accelY, accelZ, gyroX, gyroY, gyroZ)."""
        if self.address is None:
            raise RuntimeError("LSM6DS33 not initialized; call init() first")

        data = self.bus.read_i2c_block_data(self.address, _OUTX_L_G, 12)
        gx, gy, gz, ax, ay, az = struct.unpack('<hhhhhh', bytes(data))
        return ax, ay, az, gx, gy, gz
