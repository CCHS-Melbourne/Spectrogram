#![no_std]
#![no_main]

use embassy_executor::Spawner;
use esp_backtrace as _;
use esp_hal::{
    clock::ClockControl,
    dma::{Dma, DmaPriority},
    dma_buffers, embassy,
    gpio::Io,
    i2s::{DataFormat, I2s, Standard, asynch::I2sReadDmaAsync},
    peripherals::Peripherals,
    prelude::*,
    system::SystemControl,
    timer::timg::TimerGroup,
    uart::{config::Config, TxRxPins, Uart},
};

// DMA buffer size
const I2S_BYTES: usize = 4092;

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
    let (_, mut tx_descriptors, dma_rx_buffer, mut rx_descriptors) = dma_buffers!(0, I2S_BYTES * 4);

    // I2S settings
    let i2s = I2s::new(
        peripherals.I2S0,
        Standard::Philips,
        DataFormat::Data32Channel32,
        8000.Hz(),
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

    // UART settings, egress bytes as fast as possible
    let uart_config = Config::default().baudrate(921_600);
    // On Lolin S3 1.0.0, no ::default() for this
    let uart_pins = Some(TxRxPins::new_tx_rx(io.pins.gpio43, io.pins.gpio44));
    let uart0 = Uart::new_async_with_config(peripherals.UART0, uart_config, uart_pins, &clocks);
    let (mut uart_tx, _rx) = uart0.split();

    // I2S transactions to DMA buffers
    let mut i2s_data = [0u8; I2S_BYTES];
    let mut transaction = i2s_rx.read_dma_circular_async(dma_rx_buffer).unwrap();

    loop {
        let i2s_bytes_read = transaction.pop(&mut i2s_data).await.unwrap();
        uart_tx.write_async(&i2s_data[..i2s_bytes_read]).await.unwrap();
    }
}
