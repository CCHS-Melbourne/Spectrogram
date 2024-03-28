#![no_std]
#![no_main]
#![feature(type_alias_impl_trait)]

use embassy_executor::Spawner;
use embedded_io_async::Write;
use esp_backtrace as _;
use esp_hal::{
    clock::ClockControl,
    dma::{Dma, DmaPriority},
    dma_buffers, embassy,
    gpio::IO,
    i2s::{asynch::*, DataFormat, I2s, Standard},
    peripherals::Peripherals,
    prelude::*,
    timer::TimerGroup,
    uart::Uart
};

// #[embassy_executor::task]
// async fn writer(
//     mut tx: UartTx<'static, UART0>,
//     data: [u8; 5000]
// ) {
//     loop {
//         tx.write_all(&data).await.unwrap();
//     }
// }

#[main]
async fn main(_spawner: Spawner) {
    // Prepare all the peripherals and clocks
    let peripherals = Peripherals::take();
    let system = peripherals.SYSTEM.split();
    let clocks = ClockControl::boot_defaults(system.clock_control).freeze();
    let timg0 = TimerGroup::new(peripherals.TIMG0, &clocks);
    let io = IO::new(peripherals.GPIO, peripherals.IO_MUX);
    let dma = Dma::new(peripherals.DMA);
    let dma_channel = dma.channel0;

    embassy::init(&clocks, timg0);

    // Set DMA buffers
    let (_, mut tx_descriptors,
        dma_rx_buffer,
        mut rx_descriptors) = dma_buffers!(0, 4092 * 4);

    // I2S settings
    let i2s = I2s::new(
        peripherals.I2S0,
        Standard::Philips,
        DataFormat::Data16Channel16,
        44100u32.Hz(),
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

    let i2s_buffer = dma_rx_buffer;

    // UART settings
    let uart0 = Uart::new(peripherals.UART0, &clocks);
    let (mut tx,_rx) = uart0.split();

    // I2S transactions to DMA buffers
    let mut i2s_data = [0u8; 5000];
    let mut transaction = i2s_rx.read_dma_circular_async(i2s_buffer).unwrap();

    // Spawn tasks
    // spawner.spawn(writer(tx, i2s_data)).ok(); // FIXME: Start with all 0s? Does not sound right :/
    // spawner.spawn(leds()); // TODO: Future task

    loop {
        let _i2s_bytes_read = transaction.pop(&mut i2s_data).await.unwrap();
        tx.write_all(&i2s_data).await.unwrap();
    }
}
