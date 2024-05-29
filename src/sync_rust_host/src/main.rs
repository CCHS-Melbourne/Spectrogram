use std::{io::Write, time::Duration};

fn main() {
    let mut file = std::fs::File::create("./out.raw").unwrap();

    // change "com24" to match your port
    let mut port = serialport::new("/dev/cu.usbserial-10", 921_600).timeout(Duration::from_millis(500)).open().unwrap();

    for _ in 0..2 {
        let mut serial_buf: Vec<u8> = vec![0; 15000];
        let len = port.read(serial_buf.as_mut_slice());
    }

    port.write(&[b'S']).unwrap();

    loop {
        let mut serial_buf: Vec<u8> = vec![0; 15000];
        let len = port.read(serial_buf.as_mut_slice()).expect("Found no data!");
        file.write_all(&serial_buf[..len]).unwrap();
        println!("{len}");
    }
}
