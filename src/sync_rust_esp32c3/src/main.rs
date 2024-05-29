//! BCLK    GPIO2
//! WS      GPIO4
//! DIN     GPIO5

//% CHIPS: esp32 esp32c3 esp32c6 esp32h2 esp32s2 esp32s3

#![no_std]
#![no_main]

use esp_backtrace as _;
use esp_hal::{
    clock::ClockControl,
    dma::{Dma, DmaPriority},
    dma_buffers,
    gpio::Io,
    i2s::{DataFormat, I2s, I2sReadDma, Standard},
    peripherals::Peripherals,
    prelude::*,
    system::SystemControl, uart::{config::Config, TxRxPins, Uart},
};
use esp_println::println;

#[entry]
fn main() -> ! {
    let peripherals = Peripherals::take();
    let system = SystemControl::new(peripherals.SYSTEM);
    let clocks = ClockControl::max(system.clock_control).freeze();

    let io = Io::new(peripherals.GPIO, peripherals.IO_MUX);

    let uart_config = Config::default().baudrate(921_600);
    let uart_pins = Some(TxRxPins::new_tx_rx(io.pins.gpio21, io.pins.gpio20));
    let mut uart0 = Uart::new_with_config(peripherals.UART0, uart_config, uart_pins, &clocks, None);


    let dma = Dma::new(peripherals.DMA);
    #[cfg(any(feature = "esp32", feature = "esp32s2"))]
    let dma_channel = dma.i2s0channel;
    #[cfg(not(any(feature = "esp32", feature = "esp32s2")))]
    let dma_channel = dma.channel0;

    let (_, mut tx_descriptors, mut rx_buffer, mut rx_descriptors) = dma_buffers!(0, 4 * 4092);

    let i2s = I2s::new(
        peripherals.I2S0,
        Standard::Philips,
        DataFormat::Data32Channel32,
        8000.Hz(),
        dma_channel.configure(
            false,
            &mut tx_descriptors,
            &mut rx_descriptors,
            DmaPriority::Priority0,
        ),
        &clocks,
    );

    let mut i2s_rx = i2s
        .i2s_rx
        .with_bclk(io.pins.gpio2)
        .with_ws(io.pins.gpio4)
        .with_din(io.pins.gpio5)
        .build();

    let r = nb::block!(uart0.read_byte()).unwrap();

    let mut transfer = i2s_rx.read_dma_circular(&mut rx_buffer).unwrap();

    loop {
        let avail = transfer.available();

        if avail > 0 {
            let mut rcv = [0u8; 4092*2];
            transfer.pop(&mut rcv[..avail]).unwrap();
            uart0.write_bytes(&rcv[..avail]);
            uart0.flush_tx();
        }
    }
}
