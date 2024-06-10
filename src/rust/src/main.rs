#![no_std]
#![no_main]

use core::borrow::Borrow;

use embassy_executor::Spawner;
use esp_backtrace as _;
use esp_hal::{
    clock::{ClockControl, Clocks}, delay::Delay, dma::{Dma, DmaPriority}, dma_buffers, embassy, gpio::Io, i2s::{asynch::I2sReadDmaAsync, DataFormat, I2s, Standard}, peripherals::Peripherals, prelude::*, rmt::Rmt, system::SystemControl, timer::timg::TimerGroup, uart::{config::Config, TxRxPins, Uart}
};

use esp_hal_smartled::{smartLedBuffer, SmartLedsAdapter};
use smart_leds::{self, brightness, gamma, hsv::{hsv2rgb, Hsv}, SmartLedsWrite};

// use pancake_leds::fft::compute_fft;
// use pancake_leds::util::convert_u8_to_f32_array;
// DMA buffer size
const I2S_BYTES: usize = 4092;

#[embassy_executor::task]
async fn led_control(peripherals: &Rmt<'static>, io: &Io, clocks: &Clocks<'static>) {
    let rmt = Rmt::new_async(peripherals.RMT, 80.MHz(), &clocks).unwrap();

    // LED control
    let rmt_buffer = smartLedBuffer!(1);
    let led = SmartLedsAdapter::new(rmt.channel0, io.pins.gpio38, rmt_buffer, &clocks);
    
    let delay = Delay::new(&clocks);
    let mut color = Hsv {
        hue: 0,
        sat: 255,
        val: 255,
    };
    let mut data;

    loop {
        // Iterate over the rainbow!
        for hue in 0..=255 {
            color.hue = hue;
            // Convert from the HSV color space (where we can easily transition from one
            // color to the other) to the RGB color space that we can then send to the LED
            data = [hsv2rgb(color)];
            // When sending to the LED, we do a gamma correction first (see smart_leds
            // documentation for details) and then limit the brightness to 10 out of 255 so
            // that the output it's not too bright.
            led.write(brightness(gamma(data.iter().cloned()), 10))
                .unwrap();
            delay.delay_millis(20);
        }
    }
}

#[main]
async fn main(spawner: Spawner) {
    // Prepare all the peripherals and clocks
    let peripherals = Peripherals::take();
    let system = SystemControl::new(peripherals.SYSTEM);
    let clocks = ClockControl::boot_defaults(system.clock_control).freeze();
    let timg0 = TimerGroup::new_async(peripherals.TIMG0, &clocks);
    let io = Io::new(peripherals.GPIO, peripherals.IO_MUX);
    let dma = Dma::new(peripherals.DMA);
    let dma_channel = dma.channel0;

    embassy::init(&clocks, timg0);

    // LED task
    let rmt = peripherals.RMT.borrow();
    spawner.spawn(led_control(&rmt, &io, &clocks)).unwrap();

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
        let audio_data = &i2s_data[..i2s_bytes_read];
        uart_tx.write_async(&audio_data).await.unwrap();
        // let mut audio_data_for_fft = convert_u8_to_f32_array(&mut audio_data);
        // compute_fft(&mut audio_data_for_fft);
    }
}
