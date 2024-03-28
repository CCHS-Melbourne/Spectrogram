//! This shows how to continously receive data via I2S.
//!
//! Pins used:
//! MCLK    GPIO0 (not ESP32)
//! BCLK    GPIO2
//! WS      GPIO4
//! DIN     GPIO5
//!
//! Without an additional I2S source device you can connect 3V3 or GND to DIN
//! to read 0 or 0xFF or connect DIN to WS to read two different values.
//!
//! You can also inspect the MCLK, BCLK and WS with a logic analyzer.

//% CHIPS: esp32 esp32c3 esp32c6 esp32h2 esp32s2 esp32s3
//% FEATURES: async embassy embassy-executor-thread embassy-time-timg0 embassy-generic-timers

#![no_std]
#![no_main]
#![feature(type_alias_impl_trait)]

use core::fmt::Write;
use embassy_executor::Spawner;
use esp_backtrace as _;
use esp_hal::{
    clock::ClockControl,
    dma::{Dma, DmaPriority},
    dma_buffers, embassy,
    gpio::IO,
    i2s::{asynch::*, DataFormat, I2s, Standard},
    peripherals::{Peripherals, UART0},
    prelude::*,
    timer::TimerGroup,
    uart::{Uart, UartTx}
};

// rx_fifo_full_threshold
const READ_BUF_SIZE: usize = 64;

#[embassy_executor::task]
async fn writer(
    mut tx: UartTx<'static, UART0>,
    data: [u8; 5000]
) {
    loop {
        write!(&mut tx, "{:?}", &data).unwrap();
        embedded_io_async::Write::flush(&mut tx).await.unwrap();
    }
}

#[main]
async fn main(spawner: Spawner) {
    let peripherals = Peripherals::take();
    let system = peripherals.SYSTEM.split();
    let clocks = ClockControl::boot_defaults(system.clock_control).freeze();

    let timg0 = TimerGroup::new(peripherals.TIMG0, &clocks);
    embassy::init(&clocks, timg0);

    let io = IO::new(peripherals.GPIO, peripherals.IO_MUX);

    let dma = Dma::new(peripherals.DMA);
    #[cfg(any(feature = "esp32", feature = "esp32s2"))]
    let dma_channel = dma.i2s0channel;
    #[cfg(not(any(feature = "esp32", feature = "esp32s2")))]
    let dma_channel = dma.channel0;

    let (_, mut tx_descriptors, rx_buffer, mut rx_descriptors) = dma_buffers!(0, 4092 * 4);

    let i2s = I2s::new(
        peripherals.I2S0,
        Standard::Philips,
        DataFormat::Data16Channel16,
        esp_hal::prelude::_fugit_RateExtU32::Hz(44100),
        dma_channel.configure(
            false,
            &mut tx_descriptors,
            &mut rx_descriptors,
            DmaPriority::Priority0,
        ),
        &clocks,
    );

    let i2s_rx = i2s
        .i2s_rx
        .with_bclk(io.pins.gpio2)
        .with_ws(io.pins.gpio4)
        .with_din(io.pins.gpio5)
        .build();

    let i2s_buffer = rx_buffer;
    let mut uart0 = Uart::new(peripherals.UART0, &clocks);

    uart0
        .set_rx_fifo_full_threshold(READ_BUF_SIZE as u16)
        .unwrap();
    let (tx,_rx) = uart0.split();

    let mut i2s_data = [0u8; 5000];
    let mut transaction = i2s_rx.read_dma_circular_async(i2s_buffer).unwrap();

    spawner.spawn(writer(tx, i2s_data)).ok(); // FIXME: Start with all 0s? Does not sound right :/

    loop {
        let _i2s_bytes_read = transaction.pop(&mut i2s_data).await.unwrap();
    }
}
