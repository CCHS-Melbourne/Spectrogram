#![no_std]
#![no_main]

use embedded_io::Write;
use embassy_executor::Spawner;
use esp_backtrace as _;
use esp_hal::{
    embassy,
    clock::ClockControl,
    dma::{Dma, DmaPriority},
    dma_buffers,
    gpio::Io,
    i2s::{DataFormat, I2s, Standard, asynch::I2sReadDmaAsync},
    peripherals::Peripherals,
    prelude::*,
    system::SystemControl,
    uart::Uart,
    timer::timg::TimerGroup,
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
    let system = SystemControl::new(peripherals.SYSTEM);
    let clocks = ClockControl::boot_defaults(system.clock_control).freeze();
    let timg0 = TimerGroup::new_async(peripherals.TIMG0, &clocks);
    let io = Io::new(peripherals.GPIO, peripherals.IO_MUX);
    let dma = Dma::new(peripherals.DMA);
    let dma_channel = dma.channel0;

    embassy::init(&clocks, timg0);

    // Set DMA buffers
    let (_, mut tx_descriptors, dma_rx_buffer, mut rx_descriptors) = dma_buffers!(0, 4092 * 4);


    // I2S settings
    let i2s = I2s::new(
        peripherals.I2S0,
        Standard::Philips,
        DataFormat::Data16Channel16,
        16000u32.Hz(),
        dma_channel.configure_for_async(
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


    // UART settings
    let uart0 = Uart::new(peripherals.UART0, &clocks);
    let (mut tx, _rx) = uart0.split();

    // I2S transactions to DMA buffers
    let mut i2s_data = [0u8; 5000];
    let mut transaction = i2s_rx.read_dma_circular_async(dma_rx_buffer).unwrap();

    // Spawn tasks
    // spawner.spawn(writer(tx, i2s_data)).ok(); // FIXME: Start with all 0s? Does not sound right :/
    // spawner.spawn(leds());                    // TODO: Future concurrent task


    loop {
        let _i2s_bytes_read = transaction.pop(&mut i2s_data).await.unwrap();
        tx.write_all(&i2s_data).unwrap();
    }

}
