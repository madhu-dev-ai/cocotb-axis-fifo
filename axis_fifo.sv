module axis_fifo (
    input  logic       clk,
    input  logic       rst_n,

    // Slave side (data goes IN)
    input  logic [7:0] s_tdata,
    input  logic       s_tlast,
    input  logic       s_tvalid,
    output logic       s_tready,

    // Master side (data comes OUT)
    output logic [7:0] m_tdata,
    output logic       m_tlast,
    output logic       m_tvalid,
    input  logic       m_tready
);

    logic [8:0] mem [0:3];     // 4 entries, each = {tlast, tdata}
    logic [1:0] wr_ptr;
    logic [1:0] rd_ptr;
    logic [2:0] count;

    assign s_tready = (count != 3'd4);   // not full
    assign m_tvalid = (count != 3'd0);   // not empty
    assign m_tdata  = mem[rd_ptr][7:0];
    assign m_tlast  = mem[rd_ptr][8];

    wire push = s_tvalid && s_tready;
    wire pop  = m_tvalid && m_tready;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 2'd0;
            rd_ptr <= 2'd0;
            count  <= 3'd0;
        end else begin
            if (push) begin
                mem[wr_ptr] <= {s_tlast, s_tdata};
                wr_ptr      <= wr_ptr + 2'd1;
            end
            if (pop) begin
                rd_ptr <= rd_ptr + 2'd1;
            end
            case ({push, pop})
                2'b10:   count <= count + 3'd1;
                2'b01:   count <= count - 3'd1;
                default: count <= count;
            endcase
        end
    end

endmodule