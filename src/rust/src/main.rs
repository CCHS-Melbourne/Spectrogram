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
    uart::{Uart, config::Config, TxRxPins},
    timer::timg::TimerGroup,
};
use esp_println::println;

// DMA buffer size as returned by transaction.pop, determined empirically
const I2S_BYTES: usize = 4096;

// Snips 16-bit samples from a 32-bit mono sample stream
//
// assumption: I2S configuration for mono microphone.  e.g. I2S channelformat = ONLY_LEFT or ONLY_RIGHT
// example snip:
//   samples_in[] =  [0x44, 0x55, 0xAB, 0x77, 0x99, 0xBB, 0x11, 0x22]
//   samples_out[] = [0xAB, 0x77, 0x11, 0x22]
//   notes:
//       samples_in[] arranged in little endian format:
//           0x77 is the most significant byte of the 32-bit sample
//           0x44 is the least significant byte of the 32-bit sample
//
// returns: snipped bytes
fn snip_16_mono(samples_in: &[i16; I2S_BYTES]) -> [u8; I2S_BYTES / 2] {
    let num_samples = samples_in.len() / 4;
    let mut samples_out = [0i16; I2S_BYTES];

    for i in 0..num_samples {
        samples_out[2 * i] = samples_in[4 * i + 2];
        samples_out[2 * i + 1] = samples_in[4 * i + 3];
    }

    let mut result = [0; I2S_BYTES / 2];
    // Converts from [i16; _] to [u8; _]
    // Check if the length of samples_out matches the length of the result array
    if samples_out.len() / 2 == result.len() {
        // Copy the u16 samples to the u8 array
        for (i, chunk) in samples_out.chunks(2).enumerate() {
            let chunk_u8: [u8; 2] = [(chunk[0] >> 8) as u8, (chunk[0] & 0xFF) as u8];
            if i * 2 + 2 <= result.len() { // Check if index is within bounds
                result[i * 2..i * 2 + 2].copy_from_slice(&chunk_u8);
            } else {
                break; // Exit the loop if index is out of bounds
            }        
        }
    }
    //println!("{:?}", &result);
    result
}

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
    let uart_config = Config::default().baudrate(921_600);
    let uart_pins =  Some(TxRxPins::new_tx_rx(io.pins.gpio43, io.pins.gpio44)); // On Lolin S3 1.0.0, no ::default() for this
    let uart0 = Uart::new_async_with_config(peripherals.UART0, uart_config, uart_pins, &clocks); //(peripherals.UART0, &clocks);
    let (mut uart_tx, _rx) = uart0.split();

    // I2S transactions to DMA buffers
    let mut i2s_data = [0u8; I2S_BYTES];
    let mut transaction = i2s_rx.read_dma_circular_async(dma_rx_buffer).unwrap();

    // Spawn tasks
    // spawner.spawn(writer(tx, i2s_data)).ok(); // FIXME: Start with all 0s? Does not sound right :/
    // spawner.spawn(leds());                    // TODO: Future concurrent task

    loop {
        let _i2s_bytes_read = transaction.pop(&mut i2s_data).await.unwrap();
        // let mut i16_array: [i16; I2S_BYTES] = [0; I2S_BYTES];
        // // Iterate over the u8 slice by pairs of bytes
        // for (i, chunk) in i2s_data.chunks(2).enumerate() {
        //     // Convert the pair of bytes to an i16 value
        //     let value = (chunk[0] as i16) << 8 | chunk[1] as i16;
        //     // Store the i16 value in the result array
        //     i16_array[i] = value;
        // }
        // let snipped_bytes = snip_16_mono(&i16_array);
        uart_tx.write_all(&i2s_data).unwrap();
        //uart_tx.write_all(&snipped_bytes).unwrap();
    }
}
